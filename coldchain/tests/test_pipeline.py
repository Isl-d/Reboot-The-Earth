"""Ingest, derived values and incidents, driven a tick at a time."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from coldchain import cache, config
from coldchain.schemas import Telemetry

T0 = datetime(2026, 9, 24, 18, 0, 0, tzinfo=timezone.utc)


def reading(pipeline, *, t=T0, temp=3.0, lat=25.0, lon=51.5, speed=50.0,
            door=False, fridge=True, g=0.2, truck="T102") -> Telemetry:
    return Telemetry(device_id=f"TRUCK-{truck}", truck_id=truck, timestamp=t,
                     temperature_c=temp, humidity_pct=70.0, latitude=lat,
                     longitude=lon, speed_kmh=speed, g_force=g,
                     door_open=door, refrigeration_on=fridge)


def test_reference_fleet_is_loaded_on_construction(pipeline):
    ids = [t.truck_id for t in pipeline.fleet_states()]
    assert "T102" in ids
    t102 = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert t102.product == "Fresh Chicken"
    assert t102.quantity_kg == 500
    assert t102.safe_max_temp_c == 4


def test_a_reading_updates_state_and_the_cache(pipeline):
    pipeline.handle_reading(reading(pipeline, temp=3.4))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.temperature_c == 3.4
    assert state.status == "MOVING"
    cached = cache.get_latest("T102")
    assert cached and cached["temperatureC"] == 3.4
    assert cache.get_location("T102")["latitude"] == 25.0


def test_risk_stays_unknown_until_person_4_supplies_it(pipeline):
    pipeline.handle_reading(reading(pipeline, temp=25.0))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    # This platform never invents a risk score, however hot the box is.
    assert state.risk_level == "UNKNOWN"
    assert state.risk_score is None


def test_a_posted_prediction_is_stored_and_reflected(pipeline):
    pipeline.handle_reading(reading(pipeline))
    pipeline.apply_prediction({"truckId": "T102", "riskScore": 78,
                               "riskLevel": "HIGH",
                               "spoilageProbability": 0.73})
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.risk_score == 78
    assert state.risk_level == "HIGH"
    assert cache.get_risk("T102")["spoilageProbability"] == 0.73


def test_invalid_payloads_are_recorded_not_dropped(pipeline):
    assert pipeline.handle_payload({"truckId": "T102", "temperatureC": -127.0,
                                    "latitude": 25.0, "longitude": 51.0}) is None
    assert len(pipeline.rejected) == 1
    assert pipeline.rejected[0]["reason"] == "temperature_out_of_range"


def test_distance_and_eta_are_derived(pipeline):
    pipeline.handle_reading(reading(pipeline, lat=25.00, lon=51.50))
    pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=60),
                                    lat=25.05, lon=51.50))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.derived.distance_km > 5.0        # ~5.55 km per 0.05 degrees
    assert state.derived.trip_distance_km > 5.0
    # T102 is bound for WH01, so it has a distance and an ETA.
    assert state.derived.distance_to_destination_km is not None
    assert state.derived.eta_minutes is not None


def test_eta_falls_back_to_a_cruising_speed_when_stationary(pipeline):
    pipeline.handle_reading(reading(pipeline, speed=0.0))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.status == "STOPPED"
    assert state.derived.eta_minutes is not None   # never infinite
    assert state.derived.eta_minutes > 0


def test_time_above_threshold_and_thermal_exposure_accumulate(pipeline):
    # 4 C is T102's safe maximum; sit at 10 C for two minutes.
    for i in range(3):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=60 * i),
                                        temp=10.0))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.derived.time_above_threshold_s == 120.0
    # E_T = (10-4) degrees * 2 minutes = 12 degree-minutes.
    assert abs(state.derived.thermal_exposure_c_min - 12.0) < 0.01
    assert state.derived.temperature_deviation_c == 6.0


def test_a_cold_truck_accumulates_no_exposure(pipeline):
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=2.0))
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.derived.time_above_threshold_s == 0.0
    assert state.derived.thermal_exposure_c_min == 0.0


def test_a_sustained_excursion_opens_one_incident(pipeline):
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=9.0))
    incidents = [i for i in pipeline.all_incidents()
                 if i.type == "TEMPERATURE_EXCURSION"]
    assert len(incidents) == 1                    # not one per reading
    assert incidents[0].severity == "CRITICAL"
    assert incidents[0].truck_id == "T102"
    assert incidents[0].peak_temperature_c >= 9.0


def test_a_brief_excursion_does_not_open_an_incident(pipeline):
    # Above the limit, but only for one 10-second step.
    pipeline.handle_reading(reading(pipeline, temp=2.0))
    pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=10), temp=9.0))
    assert not [i for i in pipeline.all_incidents()
                if i.type == "TEMPERATURE_EXCURSION"]


def test_an_excursion_closes_when_the_box_comes_back_down(pipeline):
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=9.0))
    pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=300), temp=2.0))
    inc = next(i for i in pipeline.all_incidents() if i.type == "TEMPERATURE_EXCURSION")
    assert inc.status == "CLOSED"
    assert inc.closed_at is not None


def test_a_door_left_open_opens_an_incident(pipeline):
    for i in range(6):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=3.0, door=True))
    assert [i for i in pipeline.all_incidents() if i.type == "DOOR_LEFT_OPEN"]


def test_a_short_door_opening_is_not_an_incident(pipeline):
    pipeline.handle_reading(reading(pipeline, door=True))
    pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=20), door=True))
    pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=40), door=False))
    assert not [i for i in pipeline.all_incidents() if i.type == "DOOR_LEFT_OPEN"]


def test_refrigeration_off_opens_an_incident(pipeline):
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=3.0, fridge=False))
    inc = [i for i in pipeline.all_incidents() if i.type == "REFRIGERATION_FAILURE"]
    assert inc and inc[0].severity == "CRITICAL"


def test_a_shock_opens_a_handling_incident(pipeline):
    pipeline.handle_reading(reading(pipeline, g=3.1))
    assert [i for i in pipeline.all_incidents() if i.type == "SHOCK"]


def test_broadcasts_carry_the_documented_event_names(pipeline):
    seen: list[dict] = []
    pipeline.set_broadcast(seen.append)
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=9.0))
    events = {m["event"] for m in seen}
    assert "TRUCK_STATE_UPDATED" in events
    assert "INCIDENT_CREATED" in events
    state_msg = next(m for m in seen if m["event"] == "TRUCK_STATE_UPDATED")
    for key in ("truckId", "temperatureC", "latitude", "longitude", "riskLevel"):
        assert key in state_msg


def test_the_person_4_bundle_has_everything_the_model_needs(pipeline):
    for i in range(4):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=6.0))
    bundle = pipeline.context_for("T102")
    assert set(bundle) == {"truck", "batch", "recentTelemetry", "candidateWarehouses"}
    assert bundle["batch"]["id"] == "CHK-1029"
    assert len(bundle["recentTelemetry"]) == 4
    assert bundle["candidateWarehouses"][0]["id"] == "WH01"


def test_reset_clears_incidents_and_history(pipeline):
    for i in range(5):
        pipeline.handle_reading(reading(pipeline, t=T0 + timedelta(seconds=30 * i),
                                        temp=9.0))
    assert pipeline.all_incidents()
    pipeline.reset()
    assert not pipeline.all_incidents()
    assert not pipeline.telemetry("T102")
    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.derived.thermal_exposure_c_min == 0.0


def test_an_unknown_truck_is_still_ingested(pipeline):
    pipeline.handle_reading(reading(pipeline, truck="T999"))
    assert any(t.truck_id == "T999" for t in pipeline.fleet_states())
