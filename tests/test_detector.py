"""Detector rules, including replays of recorded simulator traces.

The traces in tests/traces/*.json come from simulator/sim.py with seed 7, so
these tests check the detector against the exact behaviour the judges will see.
"""
import json
from pathlib import Path

import pytest

from backend import config
from backend.detector import DOOR, FAILURE, SENSOR_FAULT, TruckDetector
from backend.freshness import get_product

TRACES = Path(__file__).resolve().parent / "traces"


@pytest.fixture
def det():
    return TruckDetector("TRK-03", get_product("lettuce"))


def replay(det, rows, t0=0.0):
    """Feed a recorded trace, returning every event it produced."""
    events = []
    for r in rows:
        events += det.update(t0 + r["t"], r["air_c"], r.get("door_open", False))
    return events


def load(name):
    return json.loads((TRACES / f"{name}.json").read_text())


def types(events):
    return [e.type for e in events]


# ------------------------------------------------------------- recorded traces
def test_steady_trace_is_quiet(det):
    assert types(replay(det, load("steady"))) == []


def test_door_trace_logs_a_door_opening_and_never_alerts(det):
    events = replay(det, load("door"))
    assert DOOR in types(events)
    assert not any(e.alert for e in events)


def test_compressor_trace_raises_one_alert_and_clears_it(det):
    events = replay(det, load("compressor"))
    failures = {e.seq: e for e in events if e.type == FAILURE}
    assert len(failures) == 1, "one episode, reported once when it opens and once when it ends"
    episode = next(iter(failures.values()))
    assert episode.alert
    assert episode.peak_c > get_product("lettuce").alert_limit_c
    # Cooling was restored at t=160 s, so the episode must be closed again.
    assert episode.ended_at is not None
    assert episode.ended_at - episode.started_at > config.FAILURE_HOLD_S


def test_compressor_trace_leaves_no_state_hanging(det):
    replay(det, load("compressor"))
    assert not det.has(FAILURE)
    assert det.sensor_ok


def test_sensor_trace_is_a_sensor_fault_not_a_failure(det):
    events = replay(det, load("sensor"))
    assert SENSOR_FAULT in types(events)
    assert not any(e.alert for e in events)
    assert det.sensor_ok is True            # cleared once real readings resume


# ---------------------------------------------------------------- unit rules
def steps(det, temps, start=0.0, step=2.0, door=False):
    events, t = [], start
    for x in temps:
        events += det.update(t, x, door)
        t += step
    return events, t


def test_a_short_rise_that_recovers_is_a_door_opening(det):
    events, t = steps(det, [2.5] * 5 + [9.0, 11.0, 10.0] + [2.5] * 3)
    door_events = [e for e in events if e.type == DOOR]
    assert len(door_events) == 1
    assert door_events[0].peak_c == 11.0
    assert not door_events[0].alert


def test_the_door_switch_alone_suppresses_the_alert(det):
    # Lid held open for longer than the failure hold: still not a failure.
    events, _ = steps(det, [2.5] * 3, door=False)
    events += steps(det, [20.0] * 30, start=6.0, door=True)[0]
    assert not any(e.alert for e in events)


def test_a_sustained_rise_with_the_door_closed_is_a_cooling_failure(det):
    hold = int(config.FAILURE_HOLD_S / 2) + 4
    events, _ = steps(det, [2.5] * 3 + [9.0, 14.0, 20.0] + [26.0] * hold)
    failures = [e for e in events if e.type == FAILURE]
    assert len(failures) == 1 and failures[0].alert


def test_the_alert_waits_for_the_hold_time(det):
    """Well under the hold time there must be no alert yet (DHT11 is slow)."""
    events, _ = steps(det, [2.5] * 3 + [26.0] * 5)      # 10 s above the limit
    assert not any(e.alert for e in events)


def test_a_falling_temperature_is_not_a_failure(det):
    """Recovering from a hot start must not be reported as a new failure."""
    det.update(0.0, 40.0)
    events, _ = steps(det, [38, 34, 30, 26, 22, 18, 14, 10, 9], start=2.0)
    assert not any(e.alert for e in events)


def test_minus_127_is_a_sensor_fault(det):
    events, _ = steps(det, [2.5, 2.4, config.SENSOR_SENTINEL_C])
    assert types(events)[-1] == SENSOR_FAULT
    assert det.sensor_ok is False


def test_a_big_jump_is_a_sensor_fault(det):
    events, _ = steps(det, [2.5, 2.4, 2.5 + config.SENSOR_JUMP_C + 5])
    assert SENSOR_FAULT in types(events)


def test_silence_is_a_sensor_fault(det):
    det.update(0.0, 2.5)
    assert det.check_timeout(config.SENSOR_GAP_S + 1) != []
    assert det.sensor_ok is False


def test_a_small_bump_below_the_limit_is_a_defrost(det):
    hold = int(config.DEFROST_MIN_S / 2) + 3
    events, _ = steps(det, [2.5] * 3 + [3.4] * hold + [2.4, 2.4])
    assert "defrost" in types(events)
    assert not any(e.alert for e in events)
