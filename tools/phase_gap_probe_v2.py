"""Bounded poll/pause observations; no sockets, packet mutation or output owner."""
import collections,copy,math,threading,time
from game_transport_diagnostics import ObservedClient

class PhaseGapProbe:
    MAX_EVENTS=65536;RING=128;CONTEXTS=8;PRE=16;POST=8
    def __init__(self,clock=time.perf_counter,max_events=MAX_EVENTS):
        if type(max_events) is not int or not 1<=max_events<=self.MAX_EVENTS:raise ValueError('Invalid phase event budget')
        self.clock=clock;self.limit=max_events;self.lock=threading.Lock()
        self.ring=collections.deque(maxlen=self.RING);self.contexts=[];self.protected_gap_seq=None
        self.records=self.polls=self.frames=self.timeouts=self.poll_errors=self.pauses=self.pause_errors=0
        self.errors=0;self.faulted=False;self.in_flight=None;self.last_end=None;self.last_frame=None
        self.max_gap=None;self.max_poll=None;self.max_pause=None;self.max_cost=0.;self.max_begin_cost=0.
        self.trigger_count=self.not_selected=self.replaced=0
    def _valid_time(self,t):
        if type(t) not in (int,float) or not math.isfinite(t):raise ValueError('Non-finite phase time')
    def begin(self,kind,requested=None):
        began=self.clock()
        with self.lock:
            try:
                if self.faulted:raise RuntimeError('Phase observation fault latched')
                if self.in_flight is not None:raise ValueError('Concurrent or unfinished producer phase')
                if self.records>=self.limit:raise ValueError('Phase event budget exhausted')
                if kind not in ('poll','pause'):raise ValueError('Unknown phase')
                if kind=='pause' and (type(requested) not in (int,float) or not math.isfinite(requested) or not 0<=requested<=1):raise ValueError('Invalid requested pause')
                start=self.clock();self._valid_time(start)
                if self.last_end is not None and start<self.last_end:raise ValueError('Phase clock reversed')
                self.in_flight=dict(kind=kind,start=start,event_index=self.records+1)
                if kind=='pause':self.in_flight['requested_seconds']=requested
                cost=self.clock()-began
                if not math.isfinite(cost) or cost<0:raise ValueError('Begin cost clock invalid')
                self.max_begin_cost=max(self.max_begin_cost,cost)
            except BaseException:
                self.errors+=1;self.faulted=True;raise
    def _retain(self,row,reasons,new_max):
        for context in self.contexts:
            if len(context['post'])<self.POST:context['post'].append(row)
        before=list(self.ring)[-self.PRE:] if reasons else [];self.ring.append(row)
        if not reasons:return
        self.trigger_count+=1
        score=max(row.get('receive_gap_seconds') or 0,row['duration_seconds'])
        context=dict(anchor=row,reasons=reasons,score_seconds=score,pre=before,post=[],pre_capacity=self.PRE,post_capacity=self.POST)
        if new_max:self.protected_gap_seq=row['event_index']
        if len(self.contexts)<self.CONTEXTS:self.contexts.append(context);return
        eligible=[c for c in self.contexts if c['anchor']['event_index']!=self.protected_gap_seq]
        weakest=min(eligible,key=lambda c:(c['score_seconds'],c['anchor']['event_index']))
        if new_max or score>weakest['score_seconds']:
            self.contexts.remove(weakest);self.contexts.append(context);self.replaced+=1
        else:self.not_selected+=1
    def finish(self,frame=None,error_type=None,ended_at=None):
        begin=self.clock();end=begin if ended_at is None else ended_at
        with self.lock:
            try:
                if self.faulted:raise RuntimeError('Phase observation fault latched')
                if self.in_flight is None:raise ValueError('No matching producer phase')
                self._valid_time(end);p=self.in_flight
                if end<p['start'] or end>begin:raise ValueError('Phase completion clock invalid')
                row=dict(event_index=p['event_index'],phase=p['kind'],start=p['start'],end=end,duration_seconds=end-p['start'])
                if not math.isfinite(row['duration_seconds']):raise ValueError('Non-finite phase duration')
                reasons=[];new_max=False
                if error_type is not None:row['error_type']=str(error_type)[:64]
                if p['kind']=='poll':
                    row['poll_index']=self.polls+1
                    row['outcome']='error' if error_type else ('timeout' if frame is None else 'frame')
                    if frame is not None:
                        at=frame['received_at'];self._valid_time(at)
                        if not p['start']<=at<=end:raise ValueError('Accepted frame outside observed poll')
                        stamp=frame['source_us'];flags=frame['flags'];count=len(frame['events'])
                        if type(stamp) is not int or not 0<=stamp<=0xffffffff or type(flags) is not int or not 0<=flags<=31 or count>8:raise ValueError('Frame metadata bounds')
                        gap=None if self.last_frame is None else at-self.last_frame['received_at']
                        if gap is not None and (not math.isfinite(gap) or gap<0):raise ValueError('Accepted receive clock invalid')
                        row.update(received_at=at,source_us=stamp,flags=flags,event_count=count,receive_gap_seconds=gap)
                        # Existing transport RTT starts AFTER sendto returns. This is
                        # host receive/decode/scheduling time, not pure radio latency.
                        rtt=frame.get('rtt_ms')
                        if type(rtt) not in (int,float) or not math.isfinite(rtt) or rtt<0:
                            raise ValueError('Missing or invalid transport RTT')
                        receive=rtt/1000
                        before=at-p['start']-receive
                        if before < -1e-9:raise ValueError('RTT exceeds observed pre-receive span')
                        row.update(transport_receive_decode_seconds=receive,
                            poll_start_to_transport_timer_seconds=max(0.,before),
                            received_to_poll_end_seconds=end-at)

                        if gap is not None and (self.max_gap is None or gap>self.max_gap['row']['receive_gap_seconds']):
                            self.max_gap=dict(row=row,previous_frame=self.last_frame);new_max=True;reasons.append('new_max_receive_gap')
                        if gap is not None and gap>=.040:reasons.append('receive_gap_at_least_40ms')
                        self.last_frame=row;self.frames+=1
                    elif error_type:self.poll_errors+=1;reasons.append('poll_error')
                    else:self.timeouts+=1;reasons.append('poll_timeout')
                    if row['duration_seconds']>=.040:reasons.append('poll_at_least_40ms')
                    self.polls+=1
                    if self.max_poll is None or row['duration_seconds']>self.max_poll['duration_seconds']:self.max_poll=row
                else:
                    row['requested_seconds']=p['requested_seconds'];self.pauses+=1
                    if error_type:self.pause_errors+=1;reasons.append('pause_error')
                    if row['duration_seconds']>=.012:reasons.append('pause_at_least_12ms')
                    if self.max_pause is None or row['duration_seconds']>self.max_pause['duration_seconds']:self.max_pause=row
                self._retain(row,reasons,new_max);self.records+=1;self.last_end=end;self.in_flight=None
                cost=self.clock()-begin
                if not math.isfinite(cost) or cost<0:raise ValueError('Record cost clock invalid')
                self.max_cost=max(self.max_cost,cost)
            except BaseException:
                self.errors+=1;self.faulted=True;raise
    def snapshot(self):
        try:
            began=self.clock()
            with self.lock:
                contexts=[dict(c,pre_complete=len(c['pre'])==self.PRE,post_complete=len(c['post'])==self.POST) for c in self.contexts]
                result=copy.deepcopy(dict(version=2,snapshot_atomic=True,base_and_detail_same_instant=False,
                    healthy=not self.faulted and not self.errors,errors=self.errors,fault_latched=self.faulted,
                    max_events=self.limit,recorded_events=self.records,poll_calls=self.polls,frames=self.frames,timeouts=self.timeouts,
                    poll_errors=self.poll_errors,pause_calls=self.pauses,pause_errors=self.pause_errors,in_flight=self.in_flight,
                    ring_capacity=self.RING,context_capacity=self.CONTEXTS,pre_rows=self.PRE,post_rows=self.POST,
                    recent_events=list(self.ring),contexts=contexts,protected_gap_event_index=self.protected_gap_seq,
                    maximum_receive_gap=self.max_gap,maximum_poll=self.max_poll,maximum_actual_pause=self.max_pause,
                    maximum_finish_observer_seconds=self.max_cost,maximum_begin_observer_seconds=self.max_begin_cost,trigger_count=self.trigger_count,
                    contexts_not_selected=self.not_selected,contexts_replaced=self.replaced,
                    packet_bytes_recorded=False,session_or_peer_recorded=False))
                cost=self.clock()-began
                if not math.isfinite(cost) or cost<0:raise ValueError('Snapshot cost clock invalid')
                result['snapshot_copy_seconds']=cost
                return result
        except BaseException:
            return dict(version=1,healthy=False,snapshot_error=True)

class GapObservedClient(ObservedClient):
    def __init__(self,client,clock=time.perf_counter,sleep=time.sleep,max_events=PhaseGapProbe.MAX_EVENTS):
        super().__init__(client,clock);self.phase_gap=PhaseGapProbe(clock,max_events);self.sleep=sleep
    def poll(self,*args,**kwargs):
        self.phase_gap.begin('poll')
        try:frame=super().poll(*args,**kwargs)
        except BaseException as exc:
            end=self.clock();self.phase_gap.finish(error_type=type(exc).__name__,ended_at=end);raise
        end=self.clock();self.phase_gap.finish(frame=frame,ended_at=end);return frame
    def pause(self,seconds):
        self.phase_gap.begin('pause',seconds)
        try:self.sleep(seconds)
        except BaseException as exc:
            end=self.clock();self.phase_gap.finish(error_type=type(exc).__name__,ended_at=end);raise
        end=self.clock();self.phase_gap.finish(ended_at=end)
    def snapshot(self):
        result=super().snapshot();result['phase_gap']=self.phase_gap.snapshot();return result
