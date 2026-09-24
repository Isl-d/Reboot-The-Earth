"""End-to-end run of the backend, from telemetry to an approved decision.

No broker and no database: telemetry is pushed straight into the ingest
pipeline and the API is driven in-process, so this is the whole demo in one
test — the same sequence the judges will watch.
"""
import asyncio
import time

import httpx
import pytest

from backend import config
from backend.freshness import get_product


def run(coro):
    return asyncio.run(coro)


async def _client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


class Clock:
    """A stage timeline the test can advance instantly."""

    def __init__(self, start: float | None = None) -> None:
        self.now = start if start is not None else time.time()

    def __call__(self) -> float:
        return self.now

    def tick(self, seconds: float) -> float:
        self.now += seconds
        return self.now


def feed(ingest, truck_id, air_c, seconds, door=False, step=2.0):
    """Push a stretch of telemetry at the real 2-second publish interval."""
    for _ in range(int(seconds / step)):
        ingest.clock.tick(step)
        ingest.handle(truck_id, {"truck_id": truck_id, "air_c": air_c,
                                 "hum_pct": 62, "door_open": door})


@pytest.fixture
def api(monkeypatch):
    """A fresh backend with MQTT and Postgres switched off."""
    monkeypatch.setattr(config, "DB_URL", "")
    import backend.main as main

    monkeypatch.setattr(main.ingest, "start", lambda: None)
    monkeypatch.setattr(main.ingest, "clock", Clock())
    main.state.reset()
    return main


def test_the_whole_demo(api):
    async def scenario():
        async with await _client(api.app) as c:
            api.state.bus.bind(asyncio.get_running_loop())

            health = (await c.get("/healthz")).json()
            assert health["ok"] and health["trucks"] == 12

            # 0:00 the box is closed and TRK-07 is healthy
            feed(api.ingest, "TRK-07", 2.5, 20)
            fleet = (await c.get("/api/fleet")).json()
            assert fleet["demo_speed"] == config.DEMO_SPEED
            truck = next(t for t in fleet["trucks"] if t["truck_id"] == "TRK-07")
            assert truck["live_sensor"] and truck["risk"] == "green"
            assert truck["lat"] and truck["lon"]

            # 0:40 the lid is lifted: a bump that recovers, and no alert
            feed(api.ingest, "TRK-07", 10.0, 6)
            feed(api.ingest, "TRK-07", 2.5, 10)
            events = (await c.get("/api/events")).json()["events"]
            assert any(e["type"] == "door" for e in events)
            assert not any(e["alert"] for e in events)
            assert (await c.get("/api/trucks/TRK-07")).json()["risk"] == "green"

            # 1:10 the sensor is held in a hand: a real cooling failure
            for step in (6, 10, 15, 20, 24, 27):
                feed(api.ingest, "TRK-07", step, 4)
            feed(api.ingest, "TRK-07", 28.0, 60)

            for _ in range(40):                      # the planner runs off-thread
                if api.state.decisions:
                    break
                await asyncio.sleep(0.05)

            events = (await c.get("/api/events")).json()["events"]
            assert any(e["type"] == "failure" and e["alert"] for e in events)

            truck = (await c.get("/api/trucks/TRK-07")).json()
            assert truck["risk"] in ("amber", "red")
            assert truck["at_risk"]
            assert truck["product_c"] < truck["air_c"]      # the pallet lags the air

            # 2:00 options A-D with numbers and a bilingual recommendation
            decisions = (await c.get("/api/decisions")).json()["decisions"]
            assert len(decisions) == 1
            decision = decisions[0]
            assert [o["key"] for o in decision["options"]] == ["A", "B", "C", "D"]
            assert decision["recommended"] == "C"
            assert decision["text_en"] and decision["text_ar"]
            assert decision["text_source"] in ("template", config.OLLAMA_MODEL)

            # 2:45 a human approves, and only then does anything change
            approved = (await c.post(f"/api/decisions/{decision['decision_id']}/approve",
                                     json={"approved_by": "dispatcher"})).json()
            assert approved["ok"]
            after = approved["truck"]
            assert after["status"] == "rerouted"
            assert after["destination_name"] != truck["destination_name"]
            assert after["reroute_geometry"] is not None
            assert after["life_on_arrival_days"] >= get_product("lettuce").min_life_on_arrival_days

            # approving twice is refused
            again = await c.post(f"/api/decisions/{decision['decision_id']}/approve", json={})
            assert again.status_code == 409

            # 3:20 the comparison screen and the audit trail
            impact = (await c.get("/api/impact")).json()
            assert impact["with_coldguard"]["kg_accepted"] == 2000
            assert impact["with_coldguard"]["co2e_saved_kg"] > 0
            assert impact["without_coldguard"]["kg_rejected"] == 2000

            audit = (await c.get("/api/audit")).json()
            assert audit["chain_ok"] and len(audit["records"]) == 2
            assert audit["records"][1]["payload"]["chosen"] == "C"

            # 3:45 the QR page on the box
            page = await c.get("/track/TRK-07")
            assert page.status_code == 200 and "TRK-07" in page.text

    run(scenario())


def test_reference_data_endpoints(api):
    async def scenario():
        async with await _client(api.app) as c:
            routes = (await c.get("/api/routes")).json()
            assert len(routes["features"]) == 6
            assert all("source" in f["properties"] for f in routes["features"])

            places = (await c.get("/api/places")).json()["places"]
            assert any(p["type"] == "food_bank" for p in places)
            assert all("source" in p for p in places)

            dispatch = (await c.get("/api/dispatch")).json()["suggestions"]
            assert len(dispatch) == 6
            assert dispatch[0]["best_departure"] != dispatch[0]["worst_departure"]

            heat = (await c.get("/api/heat")).json()
            assert heat["rows"] and "heat_risk_0_100" in heat["rows"][0]

    run(scenario())


def test_unknown_truck_and_decision_are_404(api):
    async def scenario():
        async with await _client(api.app) as c:
            assert (await c.get("/api/trucks/TRK-99")).status_code == 404
            assert (await c.get("/api/decisions/DEC-9999")).status_code == 404
            assert (await c.get("/track/TRK-99")).status_code == 404

    run(scenario())


def test_reset_puts_everything_back(api):
    async def scenario():
        async with await _client(api.app) as c:
            api.state.bus.bind(asyncio.get_running_loop())
            feed(api.ingest, "TRK-05", 2.5, 10)
            assert (await c.post("/api/demo/reset")).json()["ok"]
            fleet = (await c.get("/api/fleet")).json()
            assert fleet["totals"]["decisions"] == 0
            assert all(t["status"] == "rolling" for t in fleet["trucks"])
            assert (await c.get("/api/events")).json()["events"] == []

    run(scenario())


def test_demo_fault_validates_its_input(api):
    async def scenario():
        async with await _client(api.app) as c:
            bad = await c.post("/api/demo/fault",
                               json={"truck_id": "TRK-03", "fault": "explode", "on": True})
            assert bad.status_code == 400
            ok = await c.post("/api/demo/fault",
                              json={"truck_id": "TRK-03", "fault": "door", "on": True})
            assert ok.status_code == 200          # reports ok:false without a broker

    run(scenario())
