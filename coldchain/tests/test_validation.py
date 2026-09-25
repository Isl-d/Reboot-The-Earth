"""The data-quality gate: what gets in, what gets rejected, and why."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coldchain.ingestion.validation import ValidationError, normalize

GOOD = {
    "deviceId": "TRUCK-T102", "truckId": "T102",
    "timestamp": "2026-09-24T18:25:00Z",
    "temperatureC": 7.2, "humidityPct": 74,
    "latitude": 25.2854, "longitude": 51.5310,
    "speedKmh": 42, "gForce": 0.2,
    "doorOpen": False, "refrigerationOn": True,
}


def _now() -> datetime:
    return datetime(2026, 9, 24, 18, 25, 0, tzinfo=timezone.utc)


def test_the_documented_payload_is_accepted_verbatim():
    r = normalize(GOOD, now=_now())
    assert r.truck_id == "T102"
    assert r.temperature_c == 7.2
    assert r.humidity_pct == 74
    assert r.speed_kmh == 42
    assert r.refrigeration_on is True


def test_the_short_mqtt_spelling_is_accepted_too():
    # The brief's MQTT example uses temperature/humidity/lat/lon.
    r = normalize({"temperature": 7.2, "humidity": 74, "lat": 25.2854,
                   "lon": 51.531}, topic="coldchain/trucks/T102/telemetry",
                  now=_now())
    assert r.truck_id == "T102"
    assert r.temperature_c == 7.2
    assert r.latitude == 25.2854


def test_truck_id_is_recovered_from_the_device_id():
    payload = {k: v for k, v in GOOD.items() if k != "truckId"}
    assert normalize(payload, now=_now()).truck_id == "T102"


def test_truck_id_is_recovered_from_the_topic():
    payload = {k: v for k, v in GOOD.items() if k not in ("truckId", "deviceId")}
    r = normalize(payload, topic="coldchain/trucks/T104/telemetry", now=_now())
    assert r.truck_id == "T104"


def test_a_topic_that_contradicts_the_payload_is_a_conflict():
    with pytest.raises(ValidationError) as e:
        normalize(GOOD, topic="coldchain/trucks/T999/telemetry", now=_now())
    assert e.value.reason == "truck_id_conflict"


def test_a_reading_with_no_identity_at_all_is_rejected():
    with pytest.raises(ValidationError) as e:
        normalize({"temperatureC": 4.0, "latitude": 25.0, "longitude": 51.0},
                  now=_now())
    assert e.value.reason == "missing_truck_id"


@pytest.mark.parametrize("field,value,reason", [
    ("temperatureC", -127.0, "temperature_out_of_range"),   # the classic dead sensor
    ("temperatureC", 900.0, "temperature_out_of_range"),
    ("humidityPct", 140.0, "humidity_out_of_range"),
    ("humidityPct", -5.0, "humidity_out_of_range"),
    ("latitude", 91.0, "latitude_out_of_range"),
    ("longitude", 181.0, "longitude_out_of_range"),
    ("speedKmh", -3.0, "negative_speed"),
    ("gForce", -1.0, "negative_gforce"),
])
def test_implausible_values_are_rejected_with_a_reason(field, value, reason):
    payload = {**GOOD, field: value}
    with pytest.raises(ValidationError) as e:
        normalize(payload, now=_now())
    assert e.value.reason == reason
    assert e.value.detail                       # never an empty explanation


def test_a_timestamp_from_the_future_is_a_clock_fault():
    payload = {**GOOD, "timestamp": (_now() + timedelta(hours=1)).isoformat()}
    with pytest.raises(ValidationError) as e:
        normalize(payload, now=_now())
    assert e.value.reason == "timestamp_in_future"


def test_a_very_old_timestamp_is_rejected():
    payload = {**GOOD, "timestamp": (_now() - timedelta(days=3)).isoformat()}
    with pytest.raises(ValidationError) as e:
        normalize(payload, now=_now())
    assert e.value.reason == "timestamp_too_old"


def test_a_missing_timestamp_is_filled_in_rather_than_rejected():
    payload = {k: v for k, v in GOOD.items() if k != "timestamp"}
    assert normalize(payload, now=_now()).timestamp == _now()


def test_missing_optional_fields_get_safe_defaults():
    r = normalize({"truckId": "T102", "temperatureC": 3.0,
                   "latitude": 25.0, "longitude": 51.0}, now=_now())
    # Humidity is the exception: there is no safe default for a measurement,
    # and 0 % would plot as a real reading, so absent stays absent.
    assert r.humidity_pct is None
    assert r.speed_kmh == 0.0
    assert r.door_open is False
    assert r.refrigeration_on is True           # absence is not a failure report


def test_timestamps_are_normalized_to_utc():
    payload = {**GOOD, "timestamp": "2026-09-24T21:25:00+03:00"}
    r = normalize(payload, now=_now())
    assert r.timestamp == _now()
    assert r.timestamp.tzinfo is timezone.utc
