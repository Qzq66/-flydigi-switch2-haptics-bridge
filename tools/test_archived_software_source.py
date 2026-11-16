import copy,json,pathlib,unittest
from archived_software_source import prepare,schedule,START_INDEX,END_INDEX
from sustained_game_session import SustainedGameSession
from sustained_validation import assess_sustained
from test_live_fidelity_candidate import frame,event,NEUTRAL
ROOT=pathlib.Path(__file__).resolve().parents[1]

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events=json.loads((ROOT/'docs/FIDELITY_GAME_RUN_20261115-165425.json').read_text(encoding='utf-8'))['child']['events']

    def test_raw_fields_and_relative_offsets_unchanged(self):
        excerpt=prepare(self.events)
        self.assertEqual(len(excerpt),21)
        for (offset,raw),original in zip(excerpt,self.events[START_INDEX:END_INDEX]):
            self.assertEqual(raw.hex(),original['motors'])
            self.assertEqual(offset,original['at_us']-self.events[466]['at_us'])

    def test_repetition_only_adds_declared_time_shift(self):
        excerpt=prepare(self.events);rows=schedule(excerpt,.5,0)
        self.assertEqual(len(rows),126)
        for i in range(6):
            self.assertEqual(rows[i*21:(i+1)*21],[(offset+5500000+i*10000000,raw) for offset,raw in excerpt])

    def test_missing_or_reversed_or_unconfigured_source_rejected(self):
        with self.assertRaises(ValueError):prepare(self.events[:100])
        for key,value in [('at_us',self.events[465]['at_us']),('flags',3)]:
            bad=copy.deepcopy(self.events);bad[466][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):prepare(bad)

    def test_invalid_motor_length_rejected(self):
        bad=copy.deepcopy(self.events);bad[466]['motors']='00'
        with self.assertRaises(ValueError):prepare(bad)

    def test_full_virtual_window_passes_without_budget_changes(self):
        now=[0.];stops=[]
        s=SustainedGameSession(lambda:None,lambda l,r:None,
            lambda:(stops.append(True) or dict(runtime_disable_ack=True)),
            clock=lambda:now[0],pause=lambda n:now.__setitem__(0,now[0]+n))
        seq=0
        for i in range(101):
            now[0]=i*.005;s.feed(frame(now[0],[event(seq,round(now[0]*1e6),NEUTRAL)]));seq+=1
        s.arm(True,.5);rows=schedule(prepare(self.events),s.output.renderer.armed_at,0);index=0
        for _ in range(7502):
            now[0]=s.target;batch=[]
            while index<len(rows) and rows[index][0]<=round(now[0]*1e6):
                at,raw=rows[index];batch.append(event(seq,at,raw));seq+=1;index+=1
            s.feed(frame(now[0],batch));s.tick()
            if s.output.stopped_at is not None:break
        result=s.summary();assessment=assess_sustained(result)
        self.assertTrue(assessment['passed'],assessment)
        self.assertEqual(result['output_frames'],7500)
        self.assertEqual(result['completed_events'],6)
        self.assertEqual(stops,[True])
        self.assertTrue(all(1600<x<=1920 for x in result['active_ms']))

if __name__=='__main__':unittest.main()
