"""Game-pilot renderer boundaries using encoded motor words and synthetic time.

Tests only the renderer, not Windows child/guardian integration or actuators.
"""
import json
from bridge_runtime import Renderer, BridgeFault

checks = []
NEUTRAL = bytes.fromhex('0001404000014040')
PULSE = bytes.fromhex('801860b200000000')


def check(name, ok):
    checks.append(dict(name=name, passed=bool(ok)))
    if not ok:
        raise AssertionError(name)


def raises(kind, call):
    try:
        call()
    except kind:
        return True
    return False


def absolute(low_amp=127, high_frequency=64):
    word = (1 << 30) | (low_amp << 23) | (64 << 16) | (high_frequency << 2)
    return word.to_bytes(4, 'little')


def motor_frame(at_ms, raw):
    return dict(at_us=at_ms * 1000, motors=raw)


def frame(now_ms, events=(), flags=7):
    return dict(source_us=now_ms * 1000, received_at=now_ms / 1000,
                processed_at=now_ms / 1000, flags=flags, events=list(events))


def run(events, blocks, offset=12, flags_at=None):
    r = Renderer(prompt_ms=120, prompt_offset=offset, game_pilot=True)
    r.feed(frame(0, [motor_frame(0, NEUTRAL)]))
    output = [[], []]
    caught = None
    try:
        for i in range(blocks):
            source_ms = i * 8
            now_ms = 64 + source_ms
            batch = [motor_frame(source_ms, raw) for raw in events.get(source_ms, [])]
            r.feed(frame(now_ms, batch, (flags_at or {}).get(source_ms, 7)))
            block = r.block(now_ms / 1000)
            for side in (0, 1):
                output[side].extend(block[side])
    except BridgeFault as exc:
        caught = str(exc)
    return r, output, caught


check('game_pilot_requires_explicit_120ms', raises(ValueError, lambda: Renderer(game_pilot=True)))
check('game_pilot_rejects_unreviewed_amplitude', raises(ValueError, lambda: Renderer(prompt_ms=120, prompt_offset=13, game_pilot=True)))

for offset in (3, 5, 8, 12):
    r, pcm, error = run({0: [PULSE]}, 30, offset)
    check('one_pulse_exactly_120ms_offset_' + str(offset), error is None and r.active_total == [120, 0])
    check('amplitude_bound_and_right_neutral_' + str(offset), max(abs(v - 128) for v in pcm[0]) == offset and set(pcm[1]) == {128})
    check('empty_heartbeats_do_not_retrigger_' + str(offset), r.prompt_counts == [1, 0] and pcm[0][-80:] == [128] * 80)

r, pcm, error = run({0: [PULSE], 32: [PULSE]}, 30)
check('overlap_does_not_extend_or_queue_pulse', error is None and r.active_total == [120, 0] and r.prompt_counts == [1, 0])
r, pcm, error = run({0: [PULSE], 200: [PULSE], 400: [PULSE]}, 80)
check('three_distinct_pulses_bounded_to_360ms', error is None and r.active_total == [360, 0] and r.prompt_counts == [3, 0])
r, pcm, error = run({0: [PULSE], 200: [PULSE], 400: [PULSE], 600: [PULSE]}, 100)
check('fourth_pulse_latches_fault', error == 'calibrated prompt count cap' and r.prompt_counts == [3, 0] and r.prompt_remaining == [0, 0])
check('faulted_renderer_cannot_restart', raises(BridgeFault, lambda: r.feed(frame(1000))))

both = absolute() * 2
r, pcm, error = run({0: [both], 1000: [NEUTRAL]}, 140)
check('continuous_source_exactly_1000ms_allowed', error is None and r.source_active_total == [1000, 1000] and r.active_total == [120, 120])
r, pcm, error = run({0: [both]}, 140)
check('continuous_source_1001st_sample_faults', error == 'first-test active energy duration cap' and r.source_active_run[0] == 1001 and r.prompt_remaining == [0, 0])
r, pcm, error = run({0: [both], 1000: [NEUTRAL], 1008: [both], 2008: [NEUTRAL], 2016: [both], 3016: [NEUTRAL]}, 390)
check('three_source_runs_exactly_3000ms_allowed', error is None and r.source_active_total == [3000, 3000] and r.active_total == [360, 360])
r, pcm, error = run({0: [both], 1000: [NEUTRAL], 1008: [both], 2008: [NEUTRAL], 2016: [both], 3016: [NEUTRAL], 3024: [both]}, 400)
check('cumulative_3001st_source_sample_faults_before_extra_pulse', error == 'first-test active energy duration cap' and r.source_active_total[0] == 3001 and r.prompt_counts == [3, 3])

r, pcm, error = run({0: [both]}, 2, flags_at={8: 3})
check('disable_cancels_both_sides_mid_pulse', error is None and r.active_total == [8, 8] and pcm[0][-8:] == [128]*8 and pcm[1][-8:] == [128]*8)
r, pcm, error = run({0: [PULSE]}, 3, flags_at={8: 3})
check('reenabling_does_not_restart_old_pulse', error is None and r.prompt_counts == [1, 0] and pcm[0][-16:] == [128]*16)
r, pcm, error = run({0: [both]}, 3, flags_at={8: 1})
check('USB_loss_latches_stop_in_game_mode', error == 'USB upstream stopped' and r.prompt_remaining == [0, 0])
r, _, _ = run({0: [both]}, 1)
check('heartbeat_loss_latches_stop_in_game_mode', raises(BridgeFault, lambda: r.block(.2)) and r.prompt_remaining == [0, 0])
r, _, _ = run({0: [both]}, 1)
check('output_clock_gap_stops_in_game_mode', raises(BridgeFault, lambda: r.block(.073)) and r.prompt_remaining == [0, 0])

# A >500Hz source can drive a fixed-frequency notification only. It is not
# replayed as >500Hz PCM and does not imply high-frequency physical fidelity.
r, pcm, error = run({0: [absolute(high_frequency=127) + bytes(4)], 8: [NEUTRAL]}, 30)
check('high_frequency_source_only_generates_bounded_notification', error is None and r.active_total == [120, 0] and max(abs(v-128) for v in pcm[0]) <= 12)

print(json.dumps(checks, indent=2))
