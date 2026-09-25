"""Regressions for what a review pass found.

Every case here was live in a path the rest of the suite did not exercise, so
each one is pinned individually rather than folded into an existing file.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from coldchain import cache, clock
from coldchain.db import models, queries, seed, session as db
from coldchain.ingestion.pipeline import Pipeline
from coldchain.ingestion.validation import ValidationError, normalize, normalize_event
from coldchain.schemas import Telemetry
from coldchain.simulator.runner import SimulationRunner

T0 = datetime(2026, 9, 25, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def wall_clock():
    yield
    clock.uninstall()


def reading(i=0, *, truck="T102", temp=3.0, g=0.2) -> Telemetry:
    return Telemetry(device_id=f"TRUCK-{truck}", truck_id=truck,
                     timestamp=T0 + timedelta(seconds=30 * i),
                     temperature_c=temp, humidity_pct=70.0, latitude=25.0,
                     longitude=51.5, speed_kmh=40.0, g_force=g,
                     door_open=False, refrigeration_on=True)


# ------------------------------------------------------- the frozen clock
def test_an_idle_runner_leaves_the_wall_clock_alone():
    """Installing the simulated clock in the constructor froze time.

    An idle service rejected a real device's correctly-stamped telemetry as
    `timestamp_in_future` once uptime passed the skew limit, and every
    timestamp-less reading shared one instant so dt was always zero.
    """
    before = clock.now()
    SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    time.sleep(0.4)
    assert not clock.is_simulated()
    assert (clock.now() - before).total_seconds() >= 0.3


def test_a_real_device_is_accepted_after_long_uptime():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    assert runner is not None
    # Six minutes past the skew limit, with the simulation never started.
    now = datetime.now(timezone.utc)
    r = normalize({"truckId": "T102", "temperatureC": 3.0, "latitude": 25.0,
                   "longitude": 51.5, "timestamp": now.isoformat()})
    assert r.temperature_c == 3.0


def test_ticking_takes_the_clock_and_stopping_gives_it_back():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    assert not clock.is_simulated()
    runner.tick()
    assert clock.is_simulated()          # a hand-driven tick drives time too
    runner.stop()
    assert not clock.is_simulated()      # released even though never started


def test_starting_and_stopping_round_trips_the_clock():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    runner.start(5.0)
    assert clock.is_simulated()
    runner.stop()
    assert not clock.is_simulated()


def test_reset_releases_the_clock():
    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    runner.tick()
    runner.reset()
    assert not clock.is_simulated()


# ------------------------------------------------------------ shock incidents
def test_every_shock_is_reported_not_just_the_first(pipeline):
    """`_open` deduped on an OPEN incident of the same type, and a shock was
    never closed, so only the first per truck was ever seen."""
    for i in range(4):
        pipeline.handle_reading(reading(i, g=3.1))
    shocks = [i for i in pipeline.all_incidents() if i.type == "SHOCK"]
    assert len(shocks) == 4


def test_a_shock_is_recorded_closed(pipeline):
    """It is over the instant it happens; leaving it OPEN would be a lie."""
    pipeline.handle_reading(reading(g=3.1))
    shock = next(i for i in pipeline.all_incidents() if i.type == "SHOCK")
    assert shock.status == "CLOSED"
    assert shock.closed_at == shock.opened_at


def test_a_sustained_excursion_still_dedupes(pipeline):
    """The instantaneous path must not weaken the one that matters."""
    for i in range(5):
        pipeline.handle_reading(reading(i, temp=9.0))
    excursions = [i for i in pipeline.all_incidents()
                  if i.type == "TEMPERATURE_EXCURSION"]
    assert len(excursions) == 1


def test_a_rising_peak_is_persisted_and_pushed():
    """A raised peak was kept in memory only, so a restart recovered a stale one."""
    db.reset()
    seen: list[dict] = []
    p = Pipeline(persist=True)
    p.set_broadcast(seen.append)
    for i, temp in enumerate((9.0, 9.0, 9.0, 20.0)):
        p.handle_reading(reading(i, temp=temp))

    inc = next(i for i in p.all_incidents() if i.type == "TEMPERATURE_EXCURSION")
    assert inc.peak_temperature_c >= 20.0
    stored = next(r for r in queries.open_incidents() if r.id == inc.id)
    assert stored.peak_temperature_c >= 20.0
    assert any(m["event"] == "INCIDENT_UPDATED" for m in seen)


# ---------------------------------------------------------------- seeding
def test_seeding_three_times_leaves_one_set_of_rows():
    """hash() is salted per process, so merge() inserted instead of updating."""
    from sqlalchemy import func, select

    db.reset()
    for _ in range(3):
        seed.seed()
    with db.session() as s:
        n = s.execute(select(func.count()).select_from(models.Inventory)).scalar()
    from coldchain import fleet
    assert n == len(fleet.BATCHES)


# -------------------------------------------------------------- timestamps
def test_history_timestamps_carry_a_timezone():
    """Without the Z a browser reads the time as local, so REST and the
    WebSocket disagreed by the viewer's offset."""
    db.reset()
    p = Pipeline(persist=True)
    for i in range(3):
        p.handle_reading(reading(i))
    rows = queries.readings("T102")
    assert rows
    for r in rows:
        assert r["timestamp"].endswith("Z")
        datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))


# ------------------------------------------------------------------ reset
def test_reset_clears_the_stream_tables_but_keeps_reference_data():
    """Reset rewinds the clock, so rows written before it sit in the future
    and `readings()` would keep serving them - a frozen chart."""
    db.reset()
    seed.seed()
    p = Pipeline(persist=True)
    for i in range(4):
        p.handle_reading(reading(i, temp=9.0))
    assert queries.readings("T102")

    queries.clear_stream_tables()
    assert queries.readings("T102") == []
    assert queries.open_incidents() == []
    # Reference data is untouched.
    assert queries.warehouses()[1] == "database"
    assert queries.batch("CHK-1029") is not None


# ------------------------------------------------------------- validation
def test_a_device_id_that_disagrees_with_the_topic_is_a_conflict():
    """Only the payload's own truckId was checked, so a derived id could
    silently override a disagreeing topic."""
    with pytest.raises(ValidationError) as exc:
        normalize({"deviceId": "TRUCK-T102", "temperatureC": 3.0,
                   "latitude": 25.0, "longitude": 51.5},
                  topic="coldchain/trucks/T999/telemetry")
    assert exc.value.reason == "truck_id_conflict"


def test_the_same_conflict_is_caught_on_the_events_topic():
    with pytest.raises(ValidationError) as exc:
        normalize_event({"deviceId": "TRUCK-T102", "type": "SHOCK"},
                        topic="coldchain/trucks/T999/events")
    assert exc.value.reason == "truck_id_conflict"


def test_missing_humidity_is_absent_not_zero():
    """0.0 % is physically implausible in a fridge and would plot as a real
    measurement on the humidity chart."""
    r = normalize({"truckId": "T102", "temperatureC": 3.0,
                   "latitude": 25.0, "longitude": 51.5})
    assert r.humidity_pct is None


def test_a_real_humidity_is_still_carried_and_range_checked():
    assert normalize({"truckId": "T102", "temperatureC": 3.0, "humidityPct": 74,
                      "latitude": 25.0, "longitude": 51.5}).humidity_pct == 74
    with pytest.raises(ValidationError) as exc:
        normalize({"truckId": "T102", "temperatureC": 3.0, "humidityPct": 140,
                   "latitude": 25.0, "longitude": 51.5})
    assert exc.value.reason == "humidity_out_of_range"


def test_a_null_humidity_survives_the_round_trip_to_the_store():
    db.reset()
    p = Pipeline(persist=True)
    p.handle_reading(Telemetry(
        device_id="TRUCK-T102", truck_id="T102", timestamp=T0,
        temperature_c=3.0, humidity_pct=None, latitude=25.0, longitude=51.5,
        speed_kmh=40.0, g_force=0.2, door_open=False, refrigeration_on=True))
    assert queries.readings("T102")[0]["humidityPct"] is None


# ------------------------------------------------------------------ cache
def test_a_value_parked_in_memory_is_still_readable():
    """The write path falls back to memory when Redis fails; the read path
    returned None on a Redis miss and stranded it."""
    cache.init("")
    cache.clear()
    cache.set_latest("T102", {"truckId": "T102", "temperatureC": 4.5})
    assert cache.get_latest("T102")["temperatureC"] == 4.5
    assert any(s.get("truckId") == "T102" for s in cache.all_latest())
