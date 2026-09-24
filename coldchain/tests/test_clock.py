"""The platform clock.

The point of this module is that an accelerated demo stays internally
consistent: if the simulator emits ten minutes of readings in one wall-clock
minute, the durations derived from those timestamps must be ten minutes, and
validation must not call them a clock fault.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coldchain import clock
from coldchain.ingestion.pipeline import Pipeline
from coldchain.simulator import scenarios
from coldchain.simulator.runner import SimulationRunner, direct_sink


@pytest.fixture(autouse=True)
def restore_wall_clock():
    yield
    clock.uninstall()


def test_the_default_clock_is_the_wall_clock():
    clock.uninstall()
    assert not clock.is_simulated()
    assert abs((clock.now() - datetime.now(timezone.utc)).total_seconds()) < 1.0


def test_a_simulated_clock_only_moves_when_advanced():
    start = datetime(2026, 9, 24, 18, 0, tzinfo=timezone.utc)
    c = clock.SimulatedClock(start)
    clock.install(c)
    assert clock.now() == start
    assert clock.now() == start                 # does not drift on its own
    c.advance(30)
    assert clock.now() == start + timedelta(seconds=30)


def test_ticking_moves_the_clock_by_the_simulated_step():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    runner.speed_multiplier = 10.0
    before = clock.now()
    runner.tick()
    # 2 s per tick at x10 is 20 simulated seconds.
    assert (clock.now() - before).total_seconds() == pytest.approx(20.0)


def test_an_accelerated_run_accumulates_real_durations():
    """The bug this module exists to prevent.

    Ticking in a tight loop takes no wall-clock time at all. If telemetry were
    stamped with the wall clock, every reading would carry the same second and
    `time_above_threshold_s` would stay at zero no matter how hot the box got.
    """
    pipeline = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(pipeline), tick_s=5.0)
    runner.set_scenario("T102", scenarios.REFRIGERATION_FAILURE)
    for _ in range(40):
        runner.tick()

    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.derived.time_above_threshold_s > 60.0
    assert state.derived.thermal_exposure_c_min > 0.0
    assert state.derived.refrigeration_off_duration_s > 60.0


def test_simulated_timestamps_are_not_rejected_as_clock_faults():
    pipeline = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(pipeline), tick_s=5.0)
    runner.speed_multiplier = 20.0
    for _ in range(50):
        runner.tick()
    # 50 ticks x 5 s x 20 is nearly an hour and a half of simulated time, far
    # past the future-skew limit if it were compared against the wall clock.
    assert pipeline.rejected == []


def test_resetting_the_runner_rewinds_its_clock():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=5.0)
    for _ in range(10):
        runner.tick()
    advanced = clock.now()
    runner.reset()
    assert clock.now() < advanced
