"""Independent adapter profile; reuses the immutable existing product budget."""
import json
from sustained_game_policy_g61 import ROOT,digest,build_game_plan as base_plan,game_child_passed as base_child_passed,game_parent_passed as base_parent_passed

def build_game_plan():
    plan=base_plan()
    plan['entry_variant']='async-phase-adapter-v1'
    plan['requires_separate_additional_trial_authorization']=True
    for name in ('dispatch_windows_entry.py','dispatch_windows_profile.py','dispatch_io_candidate.py','offline_phase_publisher.py'):
        plan['tool_sha256'][name]=digest(ROOT/'tools'/name)
    return plan

def validate_game_plan(plan):
    if plan!=build_game_plan():raise ValueError('Adapter plan or source binding changed')

def child_passed(report):
    publisher=report.get('phase_publisher',{});probe=report.get('dispatch_io',{})
    observed=(probe.get('integration_scope')=='Windows adapter candidate, not hardware accepted' and probe.get('first_fault') is None and probe.get('steps',0)>0 and len(probe.get('recent',[]))<=32)
    return (observed and publisher.get('written',0)>=1 and base_child_passed(report) and publisher.get('closed') is True and publisher.get('error') is None and publisher.get('pending_count')==0 and not report.get('adapter_cleanup_errors'))

def parent_passed(report,plan):
    return base_parent_passed(report,plan) and child_passed(report.get('child',{}))
