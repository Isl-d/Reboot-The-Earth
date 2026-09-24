"""The Person 3 API: operational data over REST, live state over WebSocket.

One FastAPI process owns the pipeline, the MQTT consumer and the simulator, so
`GET /api/trucks` and the WebSocket always agree with each other.

What this service does NOT do: predict spoilage, estimate shelf life or choose
a destination. Those come from Person 4, are posted to
`/api/internal/predictions` and `/api/internal/recommendations`, and are stored
and forwarded from here unchanged.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .. import cache, config, fleet
from ..util import camelize
from ..db import queries, seed as seeder, session as db
from ..ingestion.consumer import MqttConsumer
from ..ingestion.pipeline import Pipeline
from ..schemas import (PredictionIn, RecommendationIn, ScenarioRequest,
                       SimulationRequest)
from ..simulator.runner import SimulationRunner, direct_sink, mqtt_sink
from .ws import hub

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("coldchain.api")

pipeline = Pipeline(broadcast=hub.broadcast)
consumer = MqttConsumer(pipeline)
# The sink is decided at startup: MQTT when a broker answers, otherwise
# straight into the pipeline so the demo still runs.
runner = SimulationRunner(sink=direct_sink(pipeline))
_sink_mode = "direct"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sink_mode

    hub.bind(asyncio.get_running_loop())
    task = asyncio.create_task(hub.pump())

    db.init()
    seeder.seed()
    cache.init()

    queries.close_stale_runs()
    pipeline.load_open_incidents(queries.open_incidents())
    pipeline.load_cached_states()

    if consumer.start():
        try:
            runner.sink = mqtt_sink()
            _sink_mode = "mqtt"
        except Exception as exc:                      # noqa: BLE001
            log.warning("publishing direct instead of over MQTT (%s)", exc)
            runner.sink = direct_sink(pipeline)
            _sink_mode = "direct"
    else:
        log.info("no broker - simulator feeds the pipeline directly")

    log.info("coldchain API ready: db=%s cache=%s sink=%s",
             db.backend(), cache.backend(), _sink_mode)
    try:
        yield
    finally:
        runner.stop()
        consumer.stop()
        task.cancel()


app = FastAPI(title="ColdChain Data Platform", version="1.0.0",
              summary="Person 3: sensors, ingestion, storage and live state",
              lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# --------------------------------------------------------------- health
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "database": db.backend(),
        "timescale": db.timescale_enabled(),
        "cache": cache.backend(),
        "mqtt": {"connected": consumer.connected, "messages": consumer.messages,
                 "host": consumer.host, "port": consumer.port},
        "simulation": {"running": runner.running, "ticks": runner.ticks,
                       "speedMultiplier": runner.speed_multiplier,
                       "sink": _sink_mode},
        "publisher": (runner.sink.stats() if hasattr(runner.sink, "stats")
                      else {"mode": "direct"}),
        "rejectedReadings": len(pipeline.rejected),
    }


# --------------------------------------------------------------- trucks
@app.get("/api/trucks")
def list_trucks() -> dict:
    states = pipeline.fleet_states()
    for s in states:
        s.scenario = runner.scenario_of(s.truck_id)
    return {"trucks": [s.model_dump(by_alias=True, mode="json") for s in states]}


@app.get("/api/trucks/{truck_id}")
def get_truck(truck_id: str) -> dict:
    state = next((s for s in pipeline.fleet_states() if s.truck_id == truck_id), None)
    if state is None:
        raise HTTPException(404, f"no truck {truck_id}")
    state.scenario = runner.scenario_of(truck_id)
    out = state.model_dump(by_alias=True, mode="json")
    batch = fleet.batch_for_truck(truck_id)
    out["batch"] = camelize(batch)
    place = fleet.place_by_id(state.destination_id) if state.destination_id else None
    out["destination"] = ({"id": place.id, "name": place.name,
                           "latitude": place.lat, "longitude": place.lon}
                          if place else None)
    return out


@app.get("/api/trucks/{truck_id}/telemetry")
def get_telemetry(truck_id: str, limit: int = 200,
                  source: str = "auto") -> dict:
    """Readings for the charts, oldest first.

    History comes from `sensor_readings`, which survives a restart and is not
    capped by the live window. `source=memory` forces the in-process buffer
    (useful when the database is down), `source=db` forces the store.
    """
    if not any(s.truck_id == truck_id for s in pipeline.fleet_states()):
        raise HTTPException(404, f"no truck {truck_id}")

    points: list[dict] = []
    used = "memory"
    if source in ("auto", "db"):
        points = queries.readings(truck_id, limit=limit)
        used = "database"
    if not points and source != "db":
        points = [p.model_dump(by_alias=True, mode="json")
                  for p in pipeline.telemetry(truck_id, limit)]
        used = "memory"

    return {"truckId": truck_id, "count": len(points), "source": used,
            "points": points}


# --------------------------------------------------- reference geography
@app.get("/api/warehouses")
def list_warehouses() -> dict:
    return {"warehouses": camelize(fleet.WAREHOUSES)}


@app.get("/api/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: str) -> dict:
    w = next((w for w in fleet.WAREHOUSES if w["id"] == warehouse_id), None)
    if w is None:
        raise HTTPException(404, f"no warehouse {warehouse_id}")
    return camelize(w)


@app.get("/api/stores")
def list_stores() -> dict:
    return {"stores": camelize(fleet.STORES)}


@app.get("/api/routes")
def list_routes() -> dict:
    return {"routes": [{**camelize(r),
                        "distanceKm": round(fleet.route_length_km(r), 3)}
                       for r in fleet.ROUTES]}


# ------------------------------------------------------------ inventory
@app.get("/api/inventory")
def list_inventory() -> dict:
    rows = []
    for b in fleet.BATCHES:
        product = fleet.product_by_id(b["product_id"])
        state = next((s for s in pipeline.fleet_states()
                      if s.truck_id == b["truck_id"]), None)
        rows.append({**camelize(b),
                     "productName": product["name"] if product else b["product_id"],
                     "locationId": b["truck_id"],
                     "locationKind": "TRUCK",
                     "riskLevel": state.risk_level if state else "UNKNOWN",
                     "riskScore": state.risk_score if state else None})
    return {"inventory": rows}


@app.get("/api/inventory/{batch_id}")
def get_batch(batch_id: str) -> dict:
    b = next((b for b in fleet.BATCHES if b["id"] == batch_id), None)
    if b is None:
        raise HTTPException(404, f"no batch {batch_id}")
    product = fleet.product_by_id(b["product_id"])
    state = next((s for s in pipeline.fleet_states()
                  if s.truck_id == b["truck_id"]), None)
    return {**camelize(b),
            "productName": product["name"] if product else b["product_id"],
            "valueQarPerKg": product["value_qar_per_kg"] if product else None,
            "truck": state.model_dump(by_alias=True, mode="json") if state else None}


# ------------------------------------------------------------ incidents
@app.get("/api/incidents")
def list_incidents(status: str | None = None) -> dict:
    items = pipeline.all_incidents()
    if status:
        items = [i for i in items if i.status.upper() == status.upper()]
    return {"incidents": [i.model_dump(by_alias=True, mode="json") for i in items]}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict:
    inc = pipeline.incidents.get(incident_id)
    if inc is None:
        raise HTTPException(404, f"no incident {incident_id}")
    return inc.model_dump(by_alias=True, mode="json")


@app.get("/api/rejected")
def list_rejected() -> dict:
    """Validation failures. Bad data is logged, never silently dropped."""
    return {"rejected": pipeline.rejected[-100:]}


# ----------------------------------------------------------- simulation
_run_id: int | None = None


@app.post("/api/simulation/start")
def simulation_start(req: SimulationRequest) -> dict:
    global _run_id

    started = runner.start(req.speed_multiplier or 1.0)
    if req.scenario:
        for tid in runner.trucks:
            runner.set_scenario(tid, req.scenario)
    if started:
        _run_id = queries.start_run(req.scenario or "NORMAL",
                                    runner.speed_multiplier, runner.seed)
    return {"running": runner.running, "started": started, "runId": _run_id,
            "speedMultiplier": runner.speed_multiplier, "sink": _sink_mode}


@app.post("/api/simulation/stop")
def simulation_stop() -> dict:
    global _run_id

    stopped = runner.stop()
    if stopped:
        queries.stop_run(_run_id, datetime.now(timezone.utc))
        _run_id = None
    return {"running": runner.running, "stopped": stopped, "ticks": runner.ticks}


@app.get("/api/simulation/runs")
def simulation_runs(limit: int = 20) -> dict:
    """Every recorded run, newest first."""
    return {"runs": queries.runs(limit)}


@app.post("/api/simulation/reset")
def simulation_reset() -> dict:
    global _run_id

    queries.stop_run(_run_id, datetime.now(timezone.utc))
    _run_id = None
    runner.reset()
    pipeline.reset()
    return {"running": runner.running, "ticks": runner.ticks, "reset": True}


@app.post("/api/simulation/scenario")
def simulation_scenario(req: ScenarioRequest) -> dict:
    ok = runner.set_scenario(req.truck_id, req.scenario, req.speed_multiplier)
    if not ok:
        raise HTTPException(404, f"no simulated truck {req.truck_id}")
    return {"truckId": req.truck_id, "scenario": req.scenario,
            "speedMultiplier": runner.speed_multiplier}


@app.post("/api/simulation/tick")
def simulation_tick() -> dict:
    """Advance one tick by hand. Useful on stage and in tests."""
    payloads = runner.tick()
    return {"ticks": runner.ticks, "published": len(payloads)}


# -------------------------------------------- contract with Person 4
@app.get("/api/internal/context/{truck_id}")
def context(truck_id: str, limit: int = 60) -> dict:
    """Normalized telemetry + batch + candidate warehouses for the model."""
    bundle = pipeline.context_for(truck_id, limit=limit)
    if bundle is None:
        raise HTTPException(404, f"no truck {truck_id}")
    return bundle


@app.post("/api/internal/predictions")
def post_prediction(p: PredictionIn) -> dict:
    """Store a prediction from Person 4 and forward it to the frontend."""
    state = pipeline.apply_prediction(p.model_dump(by_alias=True, exclude_none=True))
    if state is None:
        raise HTTPException(404, f"no truck {p.truck_id}")
    return {"stored": True,
            "truck": state.model_dump(by_alias=True, mode="json")}


@app.post("/api/internal/recommendations")
def post_recommendation(r: RecommendationIn) -> dict:
    """Store a recommendation from Person 4 and forward it to the frontend."""
    payload = r.model_dump(by_alias=True)
    hub.broadcast({"event": "RECOMMENDATION_UPDATED", **payload})
    return {"stored": True, "recommendation": payload}


# ----------------------------------------------------------- websocket
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        # Open with the whole fleet so a client that connects late is not
        # blank until the next tick.
        await ws.send_json({
            "event": "HELLO",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trucks": [s.model_dump(by_alias=True, mode="json")
                       for s in pipeline.fleet_states()],
        })
        while True:
            await ws.receive_text()                  # clients are read-only
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:                                # noqa: BLE001
        hub.disconnect(ws)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT,
                log_level="info")


if __name__ == "__main__":
    main()
