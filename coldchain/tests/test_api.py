"""The REST and WebSocket surface, driven in-process.

No broker and no Postgres: the app is started with TestClient, the simulator
is ticked by hand through POST /api/simulation/tick, and everything the
frontend relies on is checked against the running app.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from coldchain.api.main import app, pipeline, runner


def wait_for(predicate, timeout: float = 10.0, interval: float = 0.05):
    """Poll until true.

    With a broker running, the API publishes over MQTT and ingestion is
    asynchronous, so a tick is not visible the instant the request returns.
    Without a broker the pipeline is fed directly and this returns at once.
    The tests must pass either way.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def client():
    with TestClient(app) as c:
        runner.stop()                    # tick by hand, deterministically
        runner.reset()                   # scenarios and truck physics too
        runner.stop()
        # With a broker in play, messages published by the previous test may
        # still be in flight. Let them land, then clear.
        time.sleep(0.3)
        pipeline.reset()
        yield c
        runner.stop()


def test_health_reports_every_dependency(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] in ("postgresql", "sqlite")
    assert body["cache"] in ("redis", "memory")
    assert "mqtt" in body and "simulation" in body


def test_trucks_are_listed_in_the_documented_shape(client):
    body = client.get("/api/trucks").json()
    assert len(body["trucks"]) >= 5
    t = next(t for t in body["trucks"] if t["truckId"] == "T102")
    # Exactly the interface Person 1 was told to code against.
    for key in ("truckId", "latitude", "longitude", "temperatureC",
                "humidityPct", "speedKmh", "riskScore", "riskLevel"):
        assert key in t


def test_one_truck_carries_its_batch_and_destination(client):
    t = client.get("/api/trucks/T102").json()
    assert t["batch"]["id"] == "CHK-1029"
    assert t["product"] == "Fresh Chicken"
    assert t["destination"]["id"] == "WH01"


def test_an_unknown_truck_is_a_404(client):
    assert client.get("/api/trucks/NOPE").status_code == 404
    assert client.get("/api/trucks/NOPE/telemetry").status_code == 404


def test_telemetry_accumulates_as_the_simulation_ticks(client):
    for _ in range(5):
        client.post("/api/simulation/tick")
    assert wait_for(
        lambda: client.get("/api/trucks/T102/telemetry").json()["count"] >= 5)
    body = client.get("/api/trucks/T102/telemetry").json()
    assert body["points"][0]["temperatureC"] is not None


def test_reference_geography_is_served(client):
    assert client.get("/api/warehouses").json()["warehouses"][0]["id"] == "WH01"
    assert client.get("/api/warehouses/WH01").json()["name"]
    assert client.get("/api/warehouses/NOPE").status_code == 404
    assert client.get("/api/stores").json()["stores"]
    routes = client.get("/api/routes").json()["routes"]
    assert routes[0]["distanceKm"] > 0


def test_inventory_lists_batches_with_their_risk(client):
    rows = client.get("/api/inventory").json()["inventory"]
    chk = next(r for r in rows if r["id"] == "CHK-1029")
    assert chk["productName"] == "Fresh Chicken"
    assert chk["quantityKg"] == 500
    assert chk["riskLevel"] == "UNKNOWN"          # until Person 4 posts one
    detail = client.get("/api/inventory/CHK-1029").json()
    assert detail["valueQarPerKg"] == 20
    assert client.get("/api/inventory/NOPE").status_code == 404


def test_a_refrigeration_failure_surfaces_as_an_incident(client):
    client.post("/api/simulation/scenario",
                json={"truckId": "T102", "scenario": "REFRIGERATION_FAILURE"})
    for _ in range(40):
        client.post("/api/simulation/tick")

    def cooling_incident() -> bool:
        kinds = {i["type"] for i in client.get("/api/incidents").json()["incidents"]}
        return "REFRIGERATION_FAILURE" in kinds or "TEMPERATURE_EXCURSION" in kinds

    assert wait_for(cooling_incident), "no cooling incident was raised"
    incidents = client.get("/api/incidents").json()["incidents"]

    one = incidents[0]
    assert client.get(f"/api/incidents/{one['id']}").status_code == 200
    assert client.get("/api/incidents/NOPE").status_code == 404
    assert client.get("/api/incidents?status=OPEN").status_code == 200


def test_the_judge_can_watch_the_temperature_climb(client):
    client.post("/api/simulation/scenario",
                json={"truckId": "T102", "scenario": "REFRIGERATION_FAILURE"})
    for _ in range(30):
        client.post("/api/simulation/tick")

    assert wait_for(
        lambda: client.get("/api/trucks/T102/telemetry").json()["count"] >= 30)
    series = [p["temperatureC"] for p in
              client.get("/api/trucks/T102/telemetry").json()["points"]]
    assert series[-1] > series[0] + 3.0           # visibly rising


def test_simulation_control_round_trips(client):
    started = client.post("/api/simulation/start",
                          json={"speedMultiplier": 2.0}).json()
    assert started["running"] is True
    assert started["speedMultiplier"] == 2.0
    assert client.post("/api/simulation/stop").json()["running"] is False
    assert client.post("/api/simulation/reset").json()["reset"] is True
    assert client.post("/api/simulation/scenario",
                       json={"truckId": "NOPE", "scenario": "NORMAL"}).status_code == 404


def test_an_invalid_scenario_name_is_refused(client):
    r = client.post("/api/simulation/scenario",
                    json={"truckId": "T102", "scenario": "MADE_UP"})
    assert r.status_code == 422                   # pydantic rejects it at the edge


def test_the_person_4_context_bundle_is_served(client):
    for _ in range(3):
        client.post("/api/simulation/tick")
    assert wait_for(lambda: len(client.get("/api/internal/context/T102")
                                .json()["recentTelemetry"]) >= 3)
    bundle = client.get("/api/internal/context/T102").json()
    assert bundle["batch"]["id"] == "CHK-1029"
    assert bundle["candidateWarehouses"]
    assert client.get("/api/internal/context/NOPE").status_code == 404


def test_a_prediction_from_person_4_reaches_the_fleet_view(client):
    client.post("/api/simulation/tick")
    wait_for(lambda: client.get("/api/trucks/T102").json()["temperatureC"] is not None)
    r = client.post("/api/internal/predictions",
                    json={"truckId": "T102", "riskScore": 78,
                          "riskLevel": "HIGH", "spoilageProbability": 0.73,
                          "remainingShelfLife": 38, "confidence": 0.9})
    assert r.status_code == 200
    t = client.get("/api/trucks/T102").json()
    assert t["riskScore"] == 78
    assert t["riskLevel"] == "HIGH"
    assert client.post("/api/internal/predictions",
                       json={"truckId": "NOPE"}).status_code == 404


def test_a_recommendation_is_accepted_for_forwarding(client):
    r = client.post("/api/internal/recommendations",
                    json={"truckId": "T102", "action": "DIVERT",
                          "destination": "WH01", "eta": 18,
                          "expectedLoss": 400, "foodSaved": 82,
                          "reasoning": "computed by the model"})
    assert r.json()["stored"] is True


def test_bad_telemetry_is_visible_rather_than_silent(client):
    pipeline.handle_payload({"truckId": "T102", "temperatureC": -127.0,
                             "latitude": 25.0, "longitude": 51.0})
    rejected = client.get("/api/rejected").json()["rejected"]
    assert rejected[-1]["reason"] == "temperature_out_of_range"


def test_the_websocket_opens_with_the_fleet_then_streams_updates(client):
    with client.websocket_connect("/ws/live") as ws:
        hello = ws.receive_json()
        assert hello["event"] == "HELLO"
        assert any(t["truckId"] == "T102" for t in hello["trucks"])

        client.post("/api/simulation/tick")
        message = ws.receive_json()
        assert message["event"] == "TRUCK_STATE_UPDATED"
        for key in ("truckId", "temperatureC", "latitude", "longitude",
                    "riskScore", "riskLevel"):
            assert key in message


def test_telemetry_says_where_it_came_from(client):
    for _ in range(4):
        client.post("/api/simulation/tick")
    assert wait_for(
        lambda: client.get("/api/trucks/T102/telemetry").json()["count"] >= 4)

    body = client.get("/api/trucks/T102/telemetry").json()
    assert body["source"] in ("database", "memory")
    # Oldest first: that is the order a chart plots.
    stamps = [p["timestamp"] for p in body["points"]]
    assert stamps == sorted(stamps)


def test_memory_is_available_as_an_explicit_fallback(client):
    for _ in range(3):
        client.post("/api/simulation/tick")
    assert wait_for(lambda: client.get(
        "/api/trucks/T102/telemetry?source=memory").json()["count"] >= 3)
    body = client.get("/api/trucks/T102/telemetry?source=memory").json()
    assert body["source"] == "memory"


def test_simulation_runs_are_recorded(client):
    started = client.post("/api/simulation/start",
                          json={"speedMultiplier": 4.0}).json()
    client.post("/api/simulation/stop")

    runs = client.get("/api/simulation/runs").json()["runs"]
    assert runs, "a started simulation should be recorded"
    if started.get("runId") is not None:
        current = next(r for r in runs if r["id"] == started["runId"])
        assert current["speedMultiplier"] == 4.0
        assert current["stoppedAt"] is not None       # stop closed it


def test_device_events_are_served_per_truck_and_fleet_wide(client):
    client.post("/api/simulation/scenario",
                json={"truckId": "T102", "scenario": "DOOR_LEFT_OPEN"})
    for _ in range(3):
        client.post("/api/simulation/tick")

    assert wait_for(lambda: client.get(
        "/api/trucks/T102/events").json()["count"] >= 1), "no device event surfaced"

    body = client.get("/api/trucks/T102/events").json()
    assert body["truckId"] == "T102"
    assert any(e["type"] == "DOOR_OPENED" for e in body["events"])
    for key in ("deviceId", "truckId", "timestamp", "type"):
        assert key in body["events"][0]

    assert client.get("/api/device-events").json()["count"] >= 1
    assert client.get("/api/trucks/NOPE/events").status_code == 404


def test_the_websocket_carries_device_events(client):
    with client.websocket_connect("/ws/live") as ws:
        assert ws.receive_json()["event"] == "HELLO"
        client.post("/api/simulation/scenario",
                    json={"truckId": "T102", "scenario": "REFRIGERATION_FAILURE"})
        client.post("/api/simulation/tick")

        seen = set()
        for _ in range(12):
            seen.add(ws.receive_json()["event"])
            if "DEVICE_EVENT" in seen:
                break
        assert "DEVICE_EVENT" in seen
