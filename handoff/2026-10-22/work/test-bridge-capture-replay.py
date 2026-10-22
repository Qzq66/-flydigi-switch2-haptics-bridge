"""Replay exported motor events with synthetic timing; no files are rewritten."""
import json
import math
import pathlib
from bridge_runtime import Renderer

ROOT = pathlib.Path(__file__).resolve().parent.parent
checks = []


def check(name, ok):
    checks.append(dict(name=name, passed=bool(ok)))
    if not ok:
        raise AssertionError(name)


events = json.loads((ROOT / 'outputs/flydigi-live-bench-child-20261022-155010.json').read_text(encoding='utf-8'))['events']
check('capture_has_303_contiguous_events', len(events) == 303 and [e['sequence'] for e in events] == list(range(303)))
for game_pilot in (False, True):
    for offset in (3, 12):
        r = Renderer(prompt_ms=120, prompt_offset=offset, game_pilot=game_pilot)
        index = 0
        flags = 3
        maximum = 0
        frames = 0
        for i in range(math.ceil(events[-1]['at_us'] / 8000) + 30):
            source_at = i * .008
            received = source_at + .010
            batch = []
            while index < len(events) and events[index]['at_us'] <= round(source_at * 1e6):
                event = events[index]
                batch.append(dict(at_us=event['at_us'], sequence=event['sequence'], motors=bytes.fromhex(event['motors'])))
                flags = event['flags']
                index += 1
            r.feed(dict(source_us=round(source_at * 1e6), received_at=received,
                        processed_at=received, events=batch, flags=flags))
            if received >= .074 - 1e-9:
                block = r.block(.074 + frames * .008)
                frames += 1
                maximum = max(maximum, max(abs(v-128) for side in block for v in side))
        suffix = '_game_' + str(game_pilot) + '_offset_' + str(offset)
        check('all_events_consumed' + suffix, index == 303)
        check('both_prompts_120ms_with_expected_bound' + suffix,
              r.prompt_counts == [1, 1] and r.active_total == [120, 120] and maximum == offset)

proof = json.loads((ROOT / 'outputs/bridge-v041-final-live-proof.json').read_text(encoding='utf-8'))
check('historical_missing_neutral_tail_is_preserved_as_counterexample',
      proof['local_motor_fields'] == 303 and proof['received_motor_fields'] == 302 and
      proof['all_fields_received'] is False and proof['final_unreceived_fields'] == ['0000000000014040'])
print(json.dumps(checks, indent=2))
