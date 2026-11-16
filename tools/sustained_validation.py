"""Independent PCM/report reconstruction plus event/session bounds."""
import math
from written_pcm_validation import reference

def assess_sustained(child):
    checks={};expected=None
    try:
        expected=reference(child);records=child['event_records']
        checks['full_window']=child['output_frames']==7500
        checks['events_distributed']=len(records)==6 and records[-1]['quiet_completed_at']-records[0]['quiet_completed_at']>=40
        checks.update(completed_six=child['completed_events']==6 and len(records)==6,
            stopped=child['output_stop_confirmed'] is True and child['muted_reason']=='60-second session completed',
            no_fault=not any(child.get(k) for k in ('output_fault','cleanup_error')),
            successful_frames=child['successful_submission_frames']==child['output_frames']==expected['recorded_frames'],
            left_pcm=child['successful_pcm_sha256'][0]==expected['left_sha256'],right_pcm=child['successful_pcm_sha256'][1]==expected['right_sha256'],
            reports=child['successful_report_sha256']==expected['report_sha256'],
            dose=child['submitted_dose']==child['squared_code_sum']==expected['squared_code_sum'],peak=0<child['peak_code']<=9,
            whole_activity=all(0<x<=1920 for x in child['active_ms']),whole_dose=all(0<x<=48000 for x in child['squared_code_sum']),
            per_event=all(all(0<=x<=320 for x in e['active_ms']) and all(0<=x<=8000 for x in e['squared_code_sum']) for e in records),
            event_totals=all(sum(e['active_ms'][i] for e in records)==child['active_ms'][i] and sum(e['squared_code_sum'][i] for e in records)==child['squared_code_sum'][i] for i in (0,1)))
    except (KeyError,TypeError,ValueError,IndexError,OverflowError):checks['required_reference_fields']=False
    return dict(passed=bool(checks) and all(checks.values()),checks=checks,expected=expected,scope='Software source to successful host submission only, not controller execution or physical fidelity.')
