"""History, run records and incident recovery — the parts that outlive a restart.

The pipeline's window is a live buffer capped at WINDOW_SIZE and lost when the
process ends. Person 2's charts and the incident panel need more than that, so
these read from the store.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coldchain import config
from coldchain.db import queries, session as db
from coldchain.ingestion.pipeline import Pipeline
from coldchain.schemas import Telemetry

T0 = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def persisted():
    """A pipeline that actually writes, against a clean store."""
    db.reset()
    return Pipeline(persist=True)


def reading(i: int, *, truck="T102", temp=3.0) -> Telemetry:
    return Telemetry(device_id=f"TRUCK-{truck}", truck_id=truck,
                     timestamp=T0 + timedelta(seconds=30 * i),
                     temperature_c=temp, humidity_pct=70.0, latitude=25.0,
                     longitude=51.5, speed_kmh=50.0, g_force=0.2,
                     door_open=False, refrigeration_on=True)


def test_readings_are_stored_and_read_back_in_chart_order(persisted):
    for i in range(10):
        persisted.handle_reading(reading(i, temp=3.0 + i))

    rows = queries.readings("T102", limit=100)
    assert len(rows) == 10
    # Oldest first, which is the order a chart plots.
    stamps = [r["timestamp"] for r in rows]
    assert stamps == sorted(stamps)
    assert rows[0]["temperatureC"] == 3.0
    assert rows[-1]["temperatureC"] == 12.0
    assert rows[0]["truckId"] == "T102"


def test_history_survives_a_new_pipeline(persisted):
    for i in range(6):
        persisted.handle_reading(reading(i))
    # A fresh Pipeline is a fresh process, as far as memory is concerned.
    fresh = Pipeline(persist=True)
    assert fresh.telemetry("T102") == []
    assert len(queries.readings("T102")) == 6


def test_history_is_not_capped_by_the_live_window(persisted):
    n = config.WINDOW_SIZE + 25
    for i in range(n):
        persisted.handle_reading(reading(i))
    assert len(persisted.telemetry("T102", limit=10_000)) == config.WINDOW_SIZE
    assert queries.reading_count("T102") == n


def test_the_limit_returns_the_most_recent_readings(persisted):
    for i in range(20):
        persisted.handle_reading(reading(i, temp=float(i)))
    rows = queries.readings("T102", limit=5)
    assert len(rows) == 5
    assert [r["temperatureC"] for r in rows] == [15.0, 16.0, 17.0, 18.0, 19.0]


def test_since_filters_by_time(persisted):
    for i in range(10):
        persisted.handle_reading(reading(i))
    rows = queries.readings("T102", since=T0 + timedelta(seconds=30 * 5))
    assert len(rows) == 5


def test_history_is_per_truck(persisted):
    for i in range(4):
        persisted.handle_reading(reading(i, truck="T102"))
    for i in range(7):
        persisted.handle_reading(reading(i, truck="T103"))
    assert len(queries.readings("T102")) == 4
    assert len(queries.readings("T103")) == 7


def test_an_unknown_truck_has_no_history(persisted):
    assert queries.readings("T999") == []
    assert queries.reading_count("T999") == 0


def test_open_incidents_are_recovered_by_a_new_pipeline(persisted):
    for i in range(5):
        persisted.handle_reading(reading(i, temp=9.0))
    opened = [i for i in persisted.all_incidents()
              if i.type == "TEMPERATURE_EXCURSION"]
    assert opened

    fresh = Pipeline(persist=True)
    assert fresh.all_incidents() == []          # memory starts empty
    loaded = fresh.load_open_incidents(queries.open_incidents())
    assert loaded >= 1
    assert any(i.type == "TEMPERATURE_EXCURSION" for i in fresh.all_incidents())


def test_recovery_does_not_create_duplicate_ids(persisted):
    for i in range(5):
        persisted.handle_reading(reading(i, temp=9.0))

    fresh = Pipeline(persist=True)
    fresh.load_open_incidents(queries.open_incidents())
    before = {i.id for i in fresh.all_incidents()}

    # A new incident on top of a recovered one must not reuse its id.
    for i in range(5, 12):
        fresh.handle_reading(reading(i, truck="T103", temp=9.0))
    after = {i.id for i in fresh.all_incidents()}
    assert len(after) == len(before) + len(after - before)
    assert len(after) > len(before)


def test_recovery_is_idempotent(persisted):
    for i in range(5):
        persisted.handle_reading(reading(i, temp=9.0))
    fresh = Pipeline(persist=True)
    fresh.load_open_incidents(queries.open_incidents())
    n = len(fresh.all_incidents())
    fresh.load_open_incidents(queries.open_incidents())
    assert len(fresh.all_incidents()) == n


def test_a_simulation_run_is_recorded_and_closed():
    db.reset()
    run_id = queries.start_run("REFRIGERATION_FAILURE", 10.0, 7)
    assert run_id is not None

    runs = queries.runs()
    assert runs[0]["id"] == run_id
    assert runs[0]["scenario"] == "REFRIGERATION_FAILURE"
    assert runs[0]["speedMultiplier"] == 10.0
    assert runs[0]["stoppedAt"] is None

    queries.stop_run(run_id, datetime.now(timezone.utc))
    assert queries.runs()[0]["stoppedAt"] is not None


def test_closing_an_unknown_run_is_harmless():
    queries.stop_run(None, datetime.now(timezone.utc))
    queries.stop_run(999_999, datetime.now(timezone.utc))


def test_recovered_incidents_carry_timezone_aware_timestamps(persisted):
    """SQLite returns naive datetimes; sorting them against aware ones raises.

    GET /api/incidents sorts by opened_at, so without normalising on the way
    in, the incident panel would 500 after a restart.
    """
    for i in range(5):
        persisted.handle_reading(reading(i, temp=9.0))

    fresh = Pipeline(persist=True)
    fresh.load_open_incidents(queries.open_incidents())
    for inc in fresh.all_incidents():
        assert inc.opened_at.tzinfo is not None
        if inc.closed_at is not None:
            assert inc.closed_at.tzinfo is not None

    # The call that actually broke: sorting a mix of recovered and new.
    for i in range(5, 12):
        fresh.handle_reading(reading(i, truck="T103", temp=9.0))
    assert fresh.all_incidents()


def test_a_run_left_open_by_a_dead_process_is_closed_at_startup(persisted):
    """Killing the service mid-run must not leave a run open forever.

    It is closed at the last evidence the run was alive - the newest reading -
    rather than at `now`, which would inflate the duration by the downtime.
    """
    for i in range(4):
        persisted.handle_reading(reading(i))
    run_id = queries.start_run("NORMAL", 1.0, 7)
    assert queries.runs()[0]["stoppedAt"] is None

    assert queries.close_stale_runs() == 1
    closed = next(r for r in queries.runs() if r["id"] == run_id)
    assert closed["stoppedAt"] is not None
    # The last reading was at T0 + 90 s, long before "now".
    assert closed["stoppedAt"].startswith("2026-09-24T12:")

    assert queries.close_stale_runs() == 0          # nothing left to close
