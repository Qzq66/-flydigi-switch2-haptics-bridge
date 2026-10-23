"""Input-only success must not accept a zero exit with a partial terminal path."""
import pathlib,sys,copy
sys.path.insert(0,str(pathlib.Path(__file__).absolute().parents[1]/'handoff/2026-10-22/work'))
from bridge_process import input_end_check_succeeded as valid
r=dict(status='PASSED_SWITCH_WIFI_INPUT_END_CHECK',ended_reason='terminal stream complete',terminal_received=True,terminal_ack_replied=True,collector_ended=True,timer_released=True,motor_output_enabled=False,output_frames=0,input_relay=dict(nonneutral_reads=2))
assert valid(r,0);checks=1
for key,value in [('terminal_received',False),('terminal_ack_replied',False),('collector_ended',False),('timer_released',False),('motor_output_enabled',True),('output_frames',1),('ended_reason',"BridgeFault('wire heartbeat timeout')"),('status','INCOMPLETE'),('cleanup_error','failed'),('input_relay',dict(nonneutral_reads=0)),('input_relay',None)]:
    bad=copy.deepcopy(r);bad[key]=value;assert not valid(bad,0),(key,value);checks+=1
assert not valid(r,1);checks+=1
assert not valid(None,0);checks+=1
print('PASSED strict input/end gate:',checks,'checks')
