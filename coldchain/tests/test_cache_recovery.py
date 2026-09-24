"""Rehydrating the fleet from Redis after a restart.

Redis holds current state so it does not have to be rebuilt (spec, section 7).
Until this existed the cache was write-only: a restarted process reported
nulls for every truck until the next reading arrived, which on stage is a
blank map.

These run against the in-memory cache backend by default; point
COLDCHAIN_REDIS_URL at a real Redis and they exercise that instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coldchain import cache
from coldchain.ingestion.pipeline import Pipeline
from coldchain.schemas import Telemetry

T0 = datetime(2026, 9, 24, 15, 0, 0, tzinfo=timezone.utc)


def reading(i: int = 0, *, truck="T102", temp=3.4) -> Telemetry:
    return Telemetry(device_id=f"TRUCK-{truck}", truck_id=truck,
                     timestamp=T0 + timedelta(seconds=30 * i),
                     temperature_c=temp, humidity_pct=71.0, latitude=25.2854,
                     longitude=51.5310, speed_kmh=42.0, g_force=0.2,
                     door_open=False, refrigeration_on=True)


@pytest.fixture
def warm():
    """A pipeline that has seen traffic, so the cache is populated."""
    p = Pipeline(persist=False)
    for i in range(4):
        p.handle_reading(reading(i, temp=3.0 + i))
    return p


def test_a_fresh_pipeline_starts_blank(warm):
    fresh = Pipeline(persist=False)
    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert t.temperature_c is None
    assert t.latitude is None


def test_the_fleet_is_restored_from_the_cache(warm):
    fresh = Pipeline(persist=False)
    restored = fresh.load_cached_states()
    assert restored >= 1

    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert t.temperature_c == 6.0          # the last reading, 3.0 + 3
    assert t.latitude == 25.2854
    assert t.longitude == 51.5310
    assert t.speed_kmh == 42.0
    assert t.refrigeration_on is True
    assert t.timestamp is not None


def test_restoring_keeps_the_reference_data(warm):
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    # The batch and limits come from fleet.py, not the cache.
    assert t.product == "Fresh Chicken"
    assert t.safe_max_temp_c == 4
    assert t.batch_id == "CHK-1029"


def test_derived_values_are_not_invented_from_the_cache(warm):
    """A carried-over accumulation would be a fiction.

    Thermal exposure and time above threshold are sums over a stream this
    process has not seen, so they start at zero and rebuild from live data
    rather than being restored as if observed here.
    """
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert t.derived.thermal_exposure_c_min == 0.0
    assert t.derived.time_above_threshold_s == 0.0
    assert t.derived.trip_distance_km == 0.0


def test_a_restored_truck_keeps_ingesting_normally(warm):
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    fresh.handle_reading(reading(10, temp=9.0))
    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert t.temperature_c == 9.0
    assert t.derived.temperature_deviation_c == 5.0    # 9 - 4


def test_person_4_risk_survives_the_restart(warm):
    warm.apply_prediction({"truckId": "T102", "riskScore": 78,
                           "riskLevel": "HIGH"})
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    t = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert t.risk_score == 78
    assert t.risk_level == "HIGH"


def test_an_empty_cache_restores_nothing_and_does_not_raise():
    cache.clear()
    fresh = Pipeline(persist=False)
    assert fresh.load_cached_states() == 0


def test_a_truck_not_in_the_reference_fleet_is_still_restored(warm):
    warm.handle_reading(reading(truck="T999"))
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    assert any(x.truck_id == "T999" for x in fresh.fleet_states())


def test_corrupt_cache_entries_are_rejected_not_stored(warm):
    """A bad row must cost only itself, and must not leak its bad value.

    Pydantic does not validate on assignment, so restoring field by field put
    the string straight into the API response — Person 1's chart would receive
    "not-a-number" where it expects a float. The cached payload is validated
    through the model instead, so the row is skipped entirely.
    """
    cache.set_latest("T103", {"truckId": "T103", "temperatureC": "not-a-number",
                              "latitude": 25.0, "longitude": 51.0})
    fresh = Pipeline(persist=False)
    assert fresh.load_cached_states() >= 1

    bad = next(x for x in fresh.fleet_states() if x.truck_id == "T103")
    assert bad.temperature_c is None          # never the string
    assert not isinstance(bad.temperature_c, str)

    # And the neighbouring truck came back regardless.
    good = next(x for x in fresh.fleet_states() if x.truck_id == "T102")
    assert good.temperature_c == 6.0


def test_restored_state_serialises_to_the_declared_types(warm):
    """What the API returns must still match the contract Person 1 codes to."""
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()
    payload = next(x for x in fresh.fleet_states()
                   if x.truck_id == "T102").model_dump(by_alias=True, mode="json")
    assert isinstance(payload["temperatureC"], float)
    assert isinstance(payload["latitude"], float)
    assert isinstance(payload["refrigerationOn"], bool)
    assert isinstance(payload["truckId"], str)


def test_an_entry_with_no_truck_id_is_skipped(warm):
    cache.set_latest("", {"temperatureC": 3.0})
    fresh = Pipeline(persist=False)
    fresh.load_cached_states()          # must not raise
    assert any(x.truck_id == "T102" for x in fresh.fleet_states())
