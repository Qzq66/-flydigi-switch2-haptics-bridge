"""Injected-output session prototype, no platform backends or device construction."""
import hashlib,time
from fidelity_network_session import StreamSession
from bounded_multi_event_renderer import BoundedMultiEventRenderer,BridgeFault
class MultiEventSession(StreamSession):
    def __init__(self,enable,send,stop,clock=time.perf_counter,pause=time.sleep):
        self.report_hash=hashlib.sha256();self.submitted=0;self.pcm_hash=[hashlib.sha256(),hashlib.sha256()];self.submitted_dose=[0,0];self.external_send=send
        super().__init__(enable,self.tracked_send,stop,clock,pause);self.renderer=BoundedMultiEventRenderer()
    def tracked_send(self,left,right):
        if self.submitted>=1900:raise BridgeFault('Session frame capacity')
        for side in (left,right):
            if len(side)!=8 or any(type(x) is not int or abs(x-128)>9 for x in side):raise BridgeFault('Session writer amplitude/shape bound')
        additions=[sum((x-128)**2 for x in side) for side in (left,right)]
        if any(a+b>24000 for a,b in zip(self.submitted_dose,additions)):raise BridgeFault('Submitted session dose bound')
        from written_pcm_probe import encode_report
        report=encode_report(left,right)
        self.external_send(left,right)
        self.report_hash.update(report)
        for i,side in enumerate((left,right)):self.pcm_hash[i].update(bytes(side));self.submitted_dose[i]+=additions[i]
        self.submitted+=1
    def feed(self,frame):
        incoming=[dict(sequence=e['sequence'],at_us=e['at_us'],motors=e['motors'].hex()) for e in frame['events']]
        if len(self.events)+len(incoming)>2725:self.abort(BridgeFault('Session source archive capacity'));return
        self.events.extend(incoming)
        if self.fault:return
        try:self.renderer.feed(frame)
        except BaseException as exc:self.abort(exc)
    def tick(self,target):
        if self.fault:return None
        now=self.clock()
        if now<target:return None
        if now-target>.004:
            self.abort(BridgeFault('Session dispatch late; no catch-up'));return None
        return super().tick(target)
    def summary(self):
        result=super().summary();r=self.renderer
        result.update(mode='bounded_three_event_prototype',completed_events=r.completed_events,
            event_records=list(r.event_records),successful_report_sha256=self.report_hash.hexdigest(),
            active_ms=list(r.lifetime_active),squared_code_sum=list(r.lifetime_dose),
            current_event_active_ms=list(r.active_total),current_event_dose=list(r.dose),
            successful_submission_frames=self.submitted,successful_pcm_sha256=[h.hexdigest() for h in self.pcm_hash],submitted_dose=list(self.submitted_dose),
            automatic_fault_recovery=False,hardware_validated=False)
        return result
