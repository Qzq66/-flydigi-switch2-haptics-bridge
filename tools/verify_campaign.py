"""Offline campaign verification. No hardware runner imported or dispatched."""
import argparse,ctypes,datetime,hashlib,json,os,pathlib,sys,tempfile,time,unittest
ROOT=pathlib.Path(__file__).absolute().parents[1]
MODULES=('test_startup_ready_game_session','test_bounded_multi_event_renderer','test_bounded_multi_event_session','test_multi_event_game_session','test_multi_game_acceptance','test_live_fidelity_candidate','test_fidelity_game','test_fidelity_network','test_fidelity_network_io','test_haptic_fidelity_candidate','test_written_pcm_probe','test_phase_gap_probe','test_phase_gap_integration','test_receive_budget12_single_variable','test_game_input_liveness','test_listener_readiness','test_bridge_desktop','test_recovered52_heartbeat','test_sustained_session.Tests','test_dispatch_failure_analysis.Tests','test_offline_phase_publisher.Tests','test_dispatch_io_candidate.Tests','test_dispatch_windows_entry.Tests','test_outer_loop_probe.Tests','test_outer_loop_attachment.Tests','test_deadline_wait_candidate.Tests','test_highres_wait_candidate.Tests','test_outer_gap_audit.Tests','test_step_budget_model.Tests','test_wake_tail_probe.Tests','test_thread_priority.Tests','test_priority_window.Tests','test_sustained_policy_g62.Tests','test_async_phase_path.Tests','test_sustained_policy_current.Tests','test_priority_game_session.Tests','test_priority_coverage_probe.Tests','test_spin_wait_probe.Tests','test_recv_spin_probe.Tests','test_sustained_game_spin_child.Tests','test_loop_probe_session.Tests','test_async_phase_path.Tests','test_async_phase_writer.Tests')
MODULES=MODULES+('test_archived_workload_profile.Tests',)
MODULES=MODULES+('test_cross_thread_fault_analysis.Tests',)
MODULES=MODULES+('test_queue_arrival_bound.Tests',)
MODULES=MODULES+('test_retained_outer_gap.Tests',)
MODULES=MODULES+('test_software_replay_source.Tests',)
MODULES=MODULES+('test_archived_software_source.Tests',)
MODULES=MODULES+('test_archived_fault_campaign.Tests',)
MODULES=MODULES+('test_offline_spin_adapter.Tests',)
MODULES=MODULES+('test_bt_discovery.DiscoveryTests',)
MODULES=MODULES+('test_switch_usb_timing.Tests',)
MODULES=MODULES+('test_switch_usb_async_writer.Tests',)
FREEZES=('MULTI_GAME_RESULT_FREEZE_2026-10-30.json','CONFIG_STAGE_RESULT_FREEZE_2026-11-15.json','SUSTAINED_FINAL_FREEZE_2026-11-15.json')

def unique_tests(suite):
    seen=set()
    def walk(s):
        for t in s:
            if isinstance(t,unittest.TestSuite):yield from walk(t)
            else:yield t
    for t in walk(suite):
        if t.id() not in seen:seen.add(t.id());yield t

def install_audit(temp_root,output,violations):
    temp_root=temp_root.resolve();output=output.resolve()
    def writable(p):
        if not isinstance(p,(str,bytes,os.PathLike)):return True
        q=pathlib.Path(os.fsdecode(p)).resolve()
        return q==output or q==temp_root or temp_root in q.parents
    def hook(event,args):
        reason=None
        if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.startfile','ctypes.dlopen','ctypes.call_function'):reason='external_io_or_native_backend'
        if event=='open':
            path,mode,flags=args
            if isinstance(path,(str,bytes,os.PathLike)):
                s=os.fsdecode(path)
                if s.startswith('\\\\.\\') or s.startswith('/dev/'):reason='device_path'
                writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
                if writing and not writable(path):reason='write_outside_test_output'
        if event in ('os.remove','os.rmdir','os.mkdir') and not writable(args[0]):reason='filesystem_mutation_outside_test_output'
        if event=='os.rename' and any(not writable(p) for p in args[:2]):reason='filesystem_rename_outside_test_output'
        if reason:
            if len(violations)<32:violations.append(dict(event=event,reason=reason))
            raise PermissionError('Offline audit denied '+event+': '+reason)
    sys.addaudithook(hook)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tier',choices=('L0','L1','L2'),default='L0');p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
    stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');output=(a.output or ROOT/'docs/campaigns/realtime-2026-11-15'/('l0-'+stamp+'.json')).absolute()
    if output.exists():raise ValueError('Evidence output exists; refusing overwrite')
    campaign_dir=ROOT/'docs/campaigns'
    if campaign_dir.resolve() not in output.resolve().parents:raise ValueError('Report must be inside docs/campaigns')
    output.parent.mkdir(parents=True,exist_ok=True)
    if a.tier!='L0':
        report=dict(passed=[],failed=[dict(code='TIER_NOT_IMPLEMENTED',classification='process',reason='L1/L2 not implemented; no hardware fallback')],warnings=[],metrics=dict(hardware_actions=0),flaky=[],classification=dict(process=1,technical=0,unknown=0))
        with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
        print('Not implemented; no hardware actions. '+str(output));return 2
    sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'tools'));start=time.perf_counter();violations=[]
    with tempfile.TemporaryDirectory(prefix='bridge-campaign-l0-') as sandbox:
        tempfile.tempdir=sandbox;install_audit(pathlib.Path(sandbox),output,violations)
        loaded=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in MODULES);suite=unittest.TestSuite(unique_tests(loaded));r=unittest.TextTestRunner(verbosity=1).run(suite)
        frozen=[]
        for name in FREEZES:
            f=json.loads((ROOT/'docs'/name).read_text(encoding='utf-8'));frozen.append(dict(file=name,matched=all(hashlib.sha256((ROOT/x['path']).read_bytes()).hexdigest()==x['sha256'] for x in f['files'])))
        elapsed=time.perf_counter()-start;failed=[dict(test=t.id(),classification='technical' if (t,e) in r.failures else 'unknown',detail=e[-1600:]) for t,e in r.failures+r.errors]
        if violations:failed.append(dict(classification='process',code='AUDIT_BOUNDARY_VIOLATION',count=len(violations)))
        if not all(x['matched'] for x in frozen):failed.append(dict(classification='technical',code='HISTORICAL_FREEZE_MISMATCH'))
        if elapsed>300:failed.append(dict(classification='process',code='L0_FIVE_MINUTE_BUDGET_EXCEEDED'))
        report=dict(tier='L0',scope='Pure offline subset; not hardware/GUI/full product acceptance',passed=['regression','historical_freezes'] if not failed else [],failed=failed,warnings=['Audit hooks are not an OS security boundary','Hardware adapter and GUI tests intentionally excluded','Single run does not establish absence of flaky tests'],metrics=dict(tests=r.testsRun,seconds=elapsed,within_five_minutes=elapsed<=300,hardware_actions=0,audit_denials=len(violations)),flaky=[],classification={k:sum(f['classification']==k for f in failed) for k in ('process','technical','unknown')},classification_labels=dict(process='procedural',technical='technical',unknown='unproven'),coverage=list(MODULES),frozen_sources=frozen,audit_violations=violations,status='PASSED_L0_OFFLINE_SUBSET' if not failed else 'INCOMPLETE')
        with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
        print(('PASS' if not failed else 'FAIL')+f" L0: {r.testsRun} tests, {elapsed:.3f}s; hardware_actions=0");print(output)
    return 0 if not report['failed'] else 1
if __name__=='__main__':raise SystemExit(main())
