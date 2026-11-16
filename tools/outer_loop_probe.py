"""Bounded pure timing probe and injected wrappers; no hardware entry."""
import collections,math,os,time
PHASES=frozenset(('sleep_or_wakeup','cancel_stat','arm_marker_stat','arm_file_read','input_processing','phase_enqueue'))
class OuterLoopProbe:
    def __init__(self,clock=time.perf_counter,capacity=256):
        if type(capacity) is not int or not 8<=capacity<=256:raise ValueError('Probe capacity8..256')
        self.clock=clock;self.rows=collections.deque(maxlen=capacity);self.sequence=0;self.anchor=None
        self.first_slow_gap=None;self.maximum_gap=None;self.errors=0
    def call(self,phase,fn,*args,**kwargs):
        if phase not in PHASES:raise ValueError('Unknown phase')
        start=self.clock();error=None
        try:return fn(*args,**kwargs)
        except BaseException as exc:error=type(exc).__name__[:80];raise
        finally:
            end=self.clock()
            if not(math.isfinite(start) and math.isfinite(end)) or end<start:raise ValueError('Invalid probe clock')
            self.sequence+=1;self.rows.append(dict(index=self.sequence,phase=phase,start=start,end=end,error=error))
            self.errors+=error is not None
    def after_tick(self):self.anchor=(self.clock(),self.sequence)
    def before_tick(self):
        if self.anchor is None:return None
        end=self.clock();start,index=self.anchor
        if not math.isfinite(end) or end<start:raise ValueError('Invalid gap clock')
        chosen=[dict(r) for r in self.rows if r['index']>index and r['start']<end and r['end']>start]
        by_phase={p:0. for p in PHASES};segments=[]
        for r in chosen:
            a=max(start,r['start']);b=min(end,r['end']);by_phase[r['phase']]+=b-a;segments.append((a,b))
        covered=0.;right=start
        for a,b in sorted(segments):
            if b>right:covered+=b-max(a,right);right=b
        gap=dict(start=start,end=end,seconds=end-start,phase_seconds=by_phase,covered_union_seconds=covered,
            unattributed_seconds=max(0.,end-start-covered),context_complete=not self.rows or self.rows[0]['index']<=index+1,rows=chosen)
        if gap['seconds']>.004 and self.first_slow_gap is None:self.first_slow_gap=gap
        if self.maximum_gap is None or gap['seconds']>self.maximum_gap['seconds']:self.maximum_gap=gap
        return gap
    def summary(self):return dict(capacity=self.rows.maxlen,records=self.sequence,retained=len(self.rows),errors=self.errors,first_slow_gap=self.first_slow_gap,maximum_gap=self.maximum_gap,scope='Call spans include scheduler delays; not pure CPU/disk/radio latency')

class TimeProxy:
    def __init__(self,base,probe):self.base=base;self.probe=probe
    def __getattr__(self,name):return getattr(self.base,name)
    def sleep(self,seconds):return self.probe.call('sleep_or_wakeup',self.base.sleep,seconds)

class MarkerPath:
    def __init__(self,path,probe,kind='arm'):self.path=path;self.probe=probe;self.kind=kind
    def __getattr__(self,name):return getattr(self.path,name)
    def __fspath__(self):return os.fspath(self.path)
    def with_suffix(self,suffix):return MarkerPath(self.path.with_suffix(suffix),self.probe,'cancel' if suffix=='.cancel' else 'arm')
    def exists(self):return self.probe.call('cancel_stat' if self.kind=='cancel' else 'arm_marker_stat',self.path.exists)
    def read_text(self,*a,**k):return self.probe.call('arm_file_read',self.path.read_text,*a,**k)

class PhasePath:
    def __init__(self,path,probe):self.path=path;self.probe=probe
    def write_text(self,*a,**k):return self.probe.call('phase_enqueue',self.path.write_text,*a,**k)

class GameProxy:
    def __init__(self,game,probe):self.game=game;self.probe=probe
    def __getattr__(self,name):return getattr(self.game,name)
    @property
    def clock(self):return self.game.clock
    @clock.setter
    def clock(self,value):self.game.clock=value
    def feed(self,frame):return self.probe.call('input_processing',self.game.feed,frame)
    def tick(self):
        self.probe.before_tick()
        try:return self.game.tick()
        finally:self.probe.after_tick()


def attach_to_private_core(core,probe):
    """Offline installation seam only; caller owns a fresh core module instance.

    Probe clock must share the game's clock domain.
    No process-wide monkeypatch. Returns restore(); does not run the core or
    create a hardware plan. Exact source binding is required before future use.
    """
    original_time=core.time;original_game=core.GameSession;original_child=core.child
    def game_factory(*args,**kwargs):return GameProxy(original_game(*args,**kwargs),probe)
    def child(plan,backup,result,phase,arm):
        code=original_child(plan,backup,result,PhasePath(phase,probe),MarkerPath(arm,probe))
        # Only annotate the new result before its parent consumes it; preserve
        # the original status, failures, and return code without reevaluation.
        import json
        data=json.loads(result.read_text(encoding='utf-8'));data['outer_loop']=probe.summary()
        result.write_text(json.dumps(data,indent=2),encoding='utf-8');return code
    core.time=TimeProxy(original_time,probe);core.GameSession=game_factory;core.child=child
    def restore():core.time=original_time;core.GameSession=original_game;core.child=original_child
    return restore
