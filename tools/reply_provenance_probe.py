"""Observe valid stale replies without accepting them or logging packet bodies."""
import collections,copy,struct,time
from wake_timing_probe import WakeObservedClient
from short_wait_transport import unpack,BridgeFault

class ReplyTracker:
    def __init__(self,session,peer,budget=.012,history_limit=512):
        self.session=session;self.peer=peer;self.budget=budget;self.limit=history_limit
        self.sends=collections.OrderedDict();self.latest_request=None;self.previous=None
        self.sent_count=0;self.valid_replies=0;self.invalid_replies=0;self.foreign_replies=0
        self.tracked_replies=0;self.untracked_replies=0;self.stale_tracked=0;self.late_tracked=0
        self.history_evictions=0;self.internal_errors=0;self.max_processing_seconds=0.
        self.recent=collections.deque(maxlen=64);self.late=collections.deque(maxlen=32);self.worst=None

    def sent(self,data,peer,start,end):
        if peer!=self.peer or len(data) not in (20,36):return
        magic,request,session,ack=struct.unpack_from('<4sIQI',data)
        if magic not in (b'BHI2',b'BHP2',b'BHE2') or session!=self.session:return
        self.sent_count+=1;self.latest_request=request
        self.sends.pop(request,None)
        self.sends[request]=dict(request=request,sent_at=end,send_call_seconds=end-start,ack=ack,kind=magic.decode('ascii'))
        if len(self.sends)>self.limit:self.sends.popitem(last=False);self.history_evictions+=1

    def received(self,data,peer,at):
        if peer!=self.peer:self.foreign_replies+=1;return
        try:
            if len(data)<20:raise BridgeFault('short response')
            request=struct.unpack_from('<I',data,16)[0]
            frame=unpack(data,self.session,request)
        except (BridgeFault,struct.error):self.invalid_replies+=1;return
        self.valid_replies+=1;sent=self.sends.get(request)
        if sent is None:self.untracked_replies+=1;return
        self.tracked_replies+=1;age=at-sent['sent_at'];current=request==self.latest_request
        self.stale_tracked+=int(not current);self.late_tracked+=int(age>self.budget)
        row=dict(sent,received_at=at,reply_age_seconds=age,belongs_to_current_request=current,
            boot=frame['boot'],board_source_us=frame['source_us'],flags=frame['flags'],event_count=len(frame['events']))
        if self.previous is not None and self.previous['boot']==row['boot']:
            row['send_interval_from_previous_reply_request_seconds']=row['sent_at']-self.previous['sent_at']
            row['host_receive_interval_seconds']=at-self.previous['received_at']
            row['board_source_interval_us']=((row['board_source_us']-self.previous['board_source_us']+0x80000000)&0xffffffff)-0x80000000
        before=list(self.recent)[-3:];self.recent.append(row)
        if age>self.budget or not current:self.late.append(row)
        if self.worst is None or age>self.worst['event']['reply_age_seconds']:
            self.worst=copy.deepcopy(dict(before=before,event=row))
        self.previous=row

    def snapshot(self):
        return dict(sent_count=self.sent_count,valid_replies=self.valid_replies,tracked_replies=self.tracked_replies,
            untracked_replies=self.untracked_replies,invalid_replies=self.invalid_replies,foreign_replies=self.foreign_replies,
            stale_tracked_replies=self.stale_tracked,over_budget_tracked_replies=self.late_tracked,
            send_history_evictions=self.history_evictions,send_history_retained=len(self.sends),
            recent=copy.deepcopy(list(self.recent)),late=copy.deepcopy(list(self.late)),worst_reply_age_context=copy.deepcopy(self.worst),
            observer_internal_errors=self.internal_errors,maximum_observer_processing_seconds=self.max_processing_seconds,
            scope='Host elapsed time from original send completion, including OS/radio waits. Board and host intervals are unsynchronised. Eviction/untracked reply does not prove loss. No nonce, input bytes, address or packet payload exported.')

class ProvenanceSocket:
    def __init__(self,sock,tracker,clock=time.perf_counter):self.sock=sock;self.tracker=tracker;self.clock=clock
    def __getattr__(self,name):return getattr(self.sock,name)
    def observe(self,call,*args):
        begin=self.clock()
        try:call(*args)
        except Exception:self.tracker.internal_errors+=1
        finally:self.tracker.max_processing_seconds=max(self.tracker.max_processing_seconds,self.clock()-begin)
    def sendto(self,data,peer):
        start=self.clock();result=self.sock.sendto(data,peer);end=self.clock()
        self.observe(self.tracker.sent,data,peer,start,end);return result
    def recvfrom(self,size):
        data,peer=self.sock.recvfrom(size);at=self.clock()
        self.observe(self.tracker.received,data,peer,at);return data,peer

class ProvenanceClient(WakeObservedClient):
    def __init__(self,client,sleep_probe,clock=time.perf_counter):
        self.reply_tracker=ReplyTracker(client.session,(client.ip,client.network.port),client.receive_budget)
        client.sock=ProvenanceSocket(client.sock,self.reply_tracker,clock)
        super().__init__(client,sleep_probe=sleep_probe,clock=clock)
    def snapshot(self):
        result=super().snapshot();result['reply_provenance']=self.reply_tracker.snapshot();return result
