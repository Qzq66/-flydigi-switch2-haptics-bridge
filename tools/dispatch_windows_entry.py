"""Independent Windows adapter. Import and --prepare never access hardware.

Live --play requires a separate explicit extra-trial authorization flag. Existing
frozen Windows code is loaded into a fresh private module, never edited globally.
"""
import argparse,hashlib,importlib.util,json,os,pathlib,sys,time
from dispatch_io_candidate import CandidateLoop
from offline_phase_publisher import PhasePublisher
from priority_window import PriorityWindow
import dispatch_windows_profile as profile61
import dispatch_windows_profile_g62 as profile62
import dispatch_windows_profile_current as profile_current
ROOT=profile61.ROOT
AUTH_KEY='FLYDIGI_DISPATCH_ADAPTER_EXTRA_TRIAL'
PRIORITY_KEY='FLYDIGI_PRIORITY_WINDOW'

def profile_for(generation):
    # 63 and later are served by one profile that binds itself to the current verified
    # baseline; the old modules stay for the historical 61/62 runs.
    generation=int(generation)
    if generation==62:return profile62
    if generation>=63:return profile_current
    return profile61

def bind_policy(core,profile):
    core.build_game_plan=profile.build_game_plan;core.validate_game_plan=profile.validate_game_plan
    # The original child evaluates its product evidence before the outer adapter
    # drains the writer. The final predicate below additionally requires close.
    core.game_child_passed=profile.base_child_passed;core.game_parent_passed=profile.parent_passed

class AsyncPhasePath:
    def __init__(self,path,publisher_factory=PhasePublisher,attempts=8,pause=0.002):
        self.path=pathlib.Path(path);self.attempts=attempts;self.pause=pause
        self.publisher=publisher_factory(self._write)
    def _write(self,payload):
        # The UI reader holds a non-delete-sharing handle on the phase file, so an
        # atomic replace can lose a race with it. Retry briefly inside the writer
        # thread; a persistent failure still surfaces as a reported error.
        temp=self.path.with_name('.'+self.path.name+'.pending');error=None
        for _ in range(self.attempts):
            try:
                temp.write_text(payload,encoding='utf-8');temp.replace(self.path);return
            except PermissionError as exc:
                error=exc;time.sleep(self.pause)
        raise error
    def write_text(self,data,*args,**kwargs):
        value=json.loads(data)
        if value.pop('clock',None)!='monotonic':raise ValueError('Invalid phase clock')
        state=value.pop('phase');self.publisher.publish(state,**value);return len(data)

class ObservedGame:
    def __init__(self,inner,publisher,priority=False):
        self.inner=inner;self.loop=CandidateLoop(inner,lambda p:None)
        self.priority=PriorityWindow() if priority else None
        # Reuse exactly one actual writer; dispose of the inert constructor sink
        # before manual arm. No actuator/backend is owned by the writer thread.
        self.loop.publisher.close();self.loop.publisher=publisher
    def __getattr__(self,name):return getattr(self.inner,name)
    def tick(self):
        return self.loop.step() if self.priority is None else self.priority.step(self.loop.step)
    def summary(self):
        result=self.inner.summary();observation=self.loop.summary()
        observation['integration_scope']='Windows adapter candidate, not hardware accepted'
        observation['source_ingestion_profiled']=False
        if self.priority is not None:observation['priority_window']=self.priority.summary()
        result['dispatch_io']=observation;return result

def load_core(generation=61):
    source=ROOT/'tools/run_sustained_game_g61.py'
    if int(generation)==61:
        freeze=json.loads((ROOT/'docs/SUSTAINED_FINAL_FREEZE_2026-11-15.json').read_text(encoding='utf-8'))
        expected=next(x['sha256'] for x in freeze['files'] if x['path']=='tools/run_sustained_game_g61.py')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('Frozen core changed')
    spec=importlib.util.spec_from_file_location('_private_dispatch_adapter_core',source)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    if int(generation)==62:
        import sustained_game_policy_g62 as policy
        core.GameSession=policy.GameSession
    elif int(generation)>=63:
        import sustained_game_policy_current as policy
        core.GameSession=policy.GameSession
    bind_policy(core,profile_for(generation))
    core.__file__=str(pathlib.Path(__file__).absolute())
    return core

def run_child(plan,backup,result,phase,arm,core=None,publisher_factory=PhasePublisher,priority=None,generation=None):
    if generation is None:
        try:generation=int(json.loads(pathlib.Path(plan).read_text())['expected_flash_generation'])
        except (OSError,KeyError,TypeError,ValueError):
            if core is None:raise
            generation=61
    profile=profile_for(generation)
    core=core or load_core(generation);original_factory=core.GameSession;games=[];phase_path=AsyncPhasePath(phase,publisher_factory);errors=[];code=1
    if priority is None:priority=os.environ.get(PRIORITY_KEY)=='1'
    def factory(*args,**kwargs):
        if games:raise RuntimeError('Only one game session per child')
        game=ObservedGame(original_factory(*args,**kwargs),phase_path.publisher,priority=priority);games.append(game);return game
    core.GameSession=factory
    try:code=core.child(plan,backup,result,phase_path,arm)
    except BaseException as exc:errors.append('child: '+type(exc).__name__)
    finally:
        core.GameSession=original_factory
        if games and games[0].output.dirty:errors.append('original child output stop unconfirmed')
        try:phase_path.publisher.close()
        except BaseException as exc:errors.append('publisher: '+type(exc).__name__)
    # This is the same new child report before its parent consumes it, not an
    # amendment to a historical report. First errors/status fields are retained.
    report=json.loads(result.read_text(encoding='utf-8')) if result.exists() else dict(status='INCOMPLETE')
    report['phase_publisher']=phase_path.publisher.summary();report['adapter_cleanup_errors']=errors
    candidate=dict(report,status='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG')
    if code==0 and profile.child_passed(candidate):report=candidate
    else:report['status']='INCOMPLETE'
    result.write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['status']=='PASSED_SWITCH_FIDELITY_CHILD_PENDING_FLASH_LOG' else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',type=pathlib.Path);g.add_argument('--play',type=pathlib.Path);g.add_argument('--child',nargs=5,type=pathlib.Path)
    p.add_argument('--picotool',type=pathlib.Path);p.add_argument('--authorize-additional-trial',action='store_true');p.add_argument('--priority-window',action='store_true')
    p.add_argument('--generation',type=int,default=61);a=p.parse_args()
    if a.generation<61:p.error('--generation must be 61 or a later verified baseline')
    if a.prepare:
        plan=profile_for(a.generation).build_game_plan()
        with a.prepare.open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2)
        print(a.prepare);return 0
    if a.child:
        if os.environ.get(AUTH_KEY)!='explicit':p.error('Internal child requires an explicitly authorized parent')
        return run_child(*a.child)
    if not a.authorize_additional_trial:p.error('Extra hardware trial is not authorized; no device opened')
    if not a.picotool:p.error('--play requires explicit picotool')
    previous=os.environ.get(AUTH_KEY);os.environ[AUTH_KEY]='explicit'
    previous_priority=os.environ.get(PRIORITY_KEY)
    if a.priority_window:os.environ[PRIORITY_KEY]='1'
    try:return load_core(a.generation).play(a.play,a.picotool)
    finally:
        if previous is None:os.environ.pop(AUTH_KEY,None)
        else:os.environ[AUTH_KEY]=previous
        if previous_priority is None:os.environ.pop(PRIORITY_KEY,None)
        else:os.environ[PRIORITY_KEY]=previous_priority
if __name__=='__main__':raise SystemExit(main())
