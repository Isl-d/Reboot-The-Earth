"""The events topic, which until now was subscribed and silently discarded.

The brief names `coldchain/trucks/{truckId}/events` but never defines its
payload, so the contract in schemas.py is ours: a device saying what it
observed, the moment it observed it. A door opening explains the temperature
reading that follows, and telemetry only arrives every 2-5 s.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from coldchain.ingestion.pipeline import Pipeline
from coldchain.ingestion.validation import ValidationError, normalize_event
from coldchain.schemas import DEVICE_EVENT_TYPES, DeviceEvent
from coldchain.simulator import scenarios
from coldchain.simulator.runner import SimulationRunner, direct_sink

NOW = datetime(2026, 9, 25, 9, 0, 0, tzinfo=timezone.utc)


def event(kind="DOOR_OPENED", truck="T102", t=NOW) -> DeviceEvent:
    return DeviceEvent(device_id=f"TRUCK-{truck}", truck_id=truck,
                       timestamp=t, type=kind)


# ------------------------------------------------------------- validation
def test_the_documented_event_is_accepted():
    e = normalize_event({"deviceId": "TRUCK-T102", "truckId": "T102",
                         "timestamp": "2026-09-25T09:00:00Z",
                         "type": "DOOR_OPENED", "detail": "lid lifted"},
                        now=NOW)
    assert e.truck_id == "T102"
    assert e.type == "DOOR_OPENED"
    assert e.detail == "lid lifted"


def test_the_type_is_case_insensitive():
    assert normalize_event({"truckId": "T102", "type": "door_closed"},
                           now=NOW).type == "DOOR_CLOSED"


def test_identity_is_recovered_from_the_topic_like_telemetry():
    e = normalize_event({"type": "SHOCK", "value": 3.1},
                        topic="coldchain/trucks/T104/events", now=NOW)
    assert e.truck_id == "T104"
    assert e.device_id == "TRUCK-T104"
    assert e.value == 3.1


def test_a_topic_that_contradicts_the_payload_is_a_conflict():
    with pytest.raises(ValidationError) as exc:
        normalize_event({"truckId": "T102", "type": "SHOCK"},
                        topic="coldchain/trucks/T999/events", now=NOW)
    assert exc.value.reason == "truck_id_conflict"


def test_an_unknown_type_is_rejected_rather_than_stored():
    """A type the dashboard cannot render is not useful data."""
    with pytest.raises(ValidationError) as exc:
        normalize_event({"truckId": "T102", "type": "SOMETHING_ELSE"}, now=NOW)
    assert exc.value.reason == "unknown_event_type"
    assert "SOMETHING_ELSE" in exc.value.detail


def test_an_event_with_no_type_is_rejected():
    with pytest.raises(ValidationError) as exc:
        normalize_event({"truckId": "T102"}, now=NOW)
    assert exc.value.reason == "missing_event_type"


def test_an_event_with_no_identity_is_rejected():
    with pytest.raises(ValidationError) as exc:
        normalize_event({"type": "DOOR_OPENED"}, now=NOW)
    assert exc.value.reason == "missing_truck_id"


def test_a_future_timestamp_is_a_clock_fault():
    with pytest.raises(ValidationError) as exc:
        normalize_event({"truckId": "T102", "type": "SHOCK",
                         "timestamp": (NOW + timedelta(hours=1)).isoformat()},
                        now=NOW)
    assert exc.value.reason == "timestamp_in_future"


def test_a_missing_timestamp_is_filled_in():
    assert normalize_event({"truckId": "T102", "type": "SHOCK"},
                           now=NOW).timestamp == NOW


@pytest.mark.parametrize("kind", DEVICE_EVENT_TYPES)
def test_every_declared_type_round_trips(kind):
    assert normalize_event({"truckId": "T102", "type": kind}, now=NOW).type == kind


# --------------------------------------------------------------- pipeline
def test_an_event_updates_the_truck_between_ticks(pipeline):
    pipeline.handle_event(event("DOOR_OPENED"))
    t = next(x for x in pipeline.fleet_states() if x.truck_id == "T102")
    assert t.door_open is True

    pipeline.handle_event(event("DOOR_CLOSED"))
    t = next(x for x in pipeline.fleet_states() if x.truck_id == "T102")
    assert t.door_open is False


def test_refrigeration_events_update_the_flag(pipeline):
    pipeline.handle_event(event("REFRIGERATION_OFF"))
    t = next(x for x in pipeline.fleet_states() if x.truck_id == "T102")
    assert t.refrigeration_on is False


def test_telemetry_stays_authoritative(pipeline):
    """An event is a hint between readings, not a competing source of truth."""
    from coldchain.schemas import Telemetry

    pipeline.handle_event(event("DOOR_OPENED"))
    pipeline.handle_reading(Telemetry(
        device_id="TRUCK-T102", truck_id="T102", timestamp=NOW,
        temperature_c=3.0, humidity_pct=70, latitude=25.0, longitude=51.5,
        speed_kmh=40, g_force=0.2, door_open=False, refrigeration_on=True))
    t = next(x for x in pipeline.fleet_states() if x.truck_id == "T102")
    assert t.door_open is False              # the reading wins


def test_events_do_not_open_incidents(pipeline):
    """Thresholds are accumulated from telemetry, which has regular timing.

    An event says a thing happened, not for how long, so driving a duration
    threshold from one would be inventing a number.
    """
    for _ in range(5):
        pipeline.handle_event(event("REFRIGERATION_OFF"))
    assert pipeline.all_incidents() == []


def test_events_are_retrievable_per_truck_and_fleet_wide(pipeline):
    pipeline.handle_event(event("DOOR_OPENED", truck="T102"))
    pipeline.handle_event(event("SHOCK", truck="T103"))
    assert len(pipeline.device_events("T102")) == 1
    assert len(pipeline.device_events("T103")) == 1
    assert len(pipeline.device_events()) == 2


def test_a_bad_event_payload_is_recorded_not_dropped(pipeline):
    assert pipeline.handle_event_payload(
        {"truckId": "T102", "type": "NONSENSE"}) is None
    assert pipeline.rejected[-1]["reason"] == "unknown_event_type"
    assert pipeline.device_events() == []


def test_events_are_broadcast_with_their_own_name(pipeline):
    seen: list[dict] = []
    pipeline.set_broadcast(seen.append)
    pipeline.handle_event(event("DOOR_OPENED"))
    names = [m["event"] for m in seen]
    assert "DEVICE_EVENT" in names
    assert "TRUCK_STATE_UPDATED" in names       # the flag changed, so the map does
    msg = next(m for m in seen if m["event"] == "DEVICE_EVENT")
    assert msg["truckId"] == "T102" and msg["type"] == "DOOR_OPENED"


def test_reset_clears_events(pipeline):
    pipeline.handle_event(event("DOOR_OPENED"))
    pipeline.reset()
    assert pipeline.device_events() == []


# ------------------------------------------------------------- end to end
def test_the_simulator_emits_events_on_a_transition():
    fleet = scenarios.build_fleet(seed=7)
    truck = fleet["T102"]
    truck.step(5.0)
    truck.drain_events()                        # clear anything from startup

    truck.set_scenario(scenarios.DOOR_LEFT_OPEN)
    truck.step(5.0)
    kinds = [e["type"] for e in truck.drain_events()]
    assert "DOOR_OPENED" in kinds
    # Draining twice must not replay them.
    assert truck.drain_events() == []


def test_the_no_broker_path_routes_events_to_the_right_handler():
    """direct_sink must route by topic exactly as the MQTT consumer does.

    Handing an event to the telemetry path rejects it for having no
    temperature, and the no-broker mode has to behave like the real one.
    """
    p = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(p), tick_s=5.0)
    runner.tick()
    runner.set_scenario("T102", scenarios.REFRIGERATION_FAILURE)
    runner.tick()

    assert p.rejected == []
    assert any(e.type == "REFRIGERATION_OFF" for e in p.device_events())
    t = next(x for x in p.fleet_states() if x.truck_id == "T102")
    assert t.refrigeration_on is False


def test_every_simulated_event_survives_validation():
    p = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(p), tick_s=5.0)
    for name in scenarios.ALL:
        for tid in runner.trucks:
            runner.set_scenario(tid, name)
        for _ in range(10):
            runner.tick()
    assert p.rejected == []
    assert p.device_events(), "the scenarios should have produced some events"
