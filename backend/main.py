"""ColdGuard backend: one FastAPI process (CLAUDE.md section 5).

REST for the dashboard, a WebSocket for live pushes, a mobile page behind the
QR code on the cooler box, and three demo endpoints so nobody types a terminal
command on stage.
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import config, geo
from .db import db
from .ingest import Ingest
from .state import state

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
log = logging.getLogger("coldguard")

ingest = Ingest(state)
templates = Jinja2Templates(directory=str(config.ROOT / "backend" / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    state.bus.bind(asyncio.get_running_loop())
    db.connect()
    for t in state.trucks.values():
        db.upsert_shipment(t.truck_id, t.product.product, t.qty_kg, t.route_id,
                           t.destination_id, None, t.life_left_h, t.status)
    ingest.start()
    log.info("ColdGuard backend ready - demo clock x%.0f", config.DEMO_SPEED)
    yield
    ingest.stop()
    db.close()


app = FastAPI(title="ColdGuard", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# --------------------------------------------------------------------- read
@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "trucks": len(state.trucks), "db": db.enabled,
            "demo_speed": config.DEMO_SPEED, "uptime_s": round(time.time() - state.started_at)}


@app.get("/api/fleet")
def fleet() -> dict:
    return {"demo_speed": config.DEMO_SPEED, "map_speed": config.MAP_SPEED,
            "real_truck": config.REAL_TRUCK, "trucks": state.fleet_dicts(),
            "totals": state.totals()}


@app.get("/api/trucks/{truck_id}")
def truck(truck_id: str) -> dict:
    t = state.trucks.get(truck_id)
    if t is None:
        raise HTTPException(404, f"unknown truck {truck_id}")
    with state.lock:
        return t.as_dict()


@app.get("/api/trucks/{truck_id}/history")
def history(truck_id: str, limit: int = 600) -> dict:
    t = state.trucks.get(truck_id)
    if t is None:
        raise HTTPException(404, f"unknown truck {truck_id}")
    with state.lock:
        points = list(t.history)[-limit:]
        events = [e for e in state.events if e["truck_id"] == truck_id][:40]
    return {"truck_id": truck_id, "alert_limit_c": t.product.alert_limit_c,
            "ideal_temp_c": t.product.ideal_temp_c, "points": points, "events": events}


@app.get("/api/places")
def places() -> dict:
    return {"places": [p.as_dict() for p in geo.load_places().values()]}


@app.get("/api/routes")
def routes() -> dict:
    """Routes as GeoJSON, straight from data/routes.geojson."""
    features = []
    for r in geo.load_routes().values():
        features.append({"type": "Feature",
                         "properties": {"route_id": r.route_id, "name": r.name,
                                        "distance_km": round(r.total_km, 1),
                                        "duration_min": r.duration_min,
                                        "source": r.source},
                         "geometry": {"type": "LineString", "coordinates": r.coords}})
    return {"type": "FeatureCollection", "features": features}


def _read_csv(name: str) -> list[dict]:
    with open(config.DATA_DIR / name, newline="") as f:
        return list(csv.DictReader(f))


@app.get("/api/heat")
def heat(route_id: str | None = None) -> dict:
    """Outside heat per route per hour - the map's heat-risk layer."""
    rows = _read_csv("heat_by_hour.csv")
    if route_id:
        rows = [r for r in rows if r["route_id"] == route_id]
    now_hour = time.strftime("%Y-%m-%dT%H:00")
    current = {r["route_id"]: r for r in rows if r["time"] <= now_hour}
    return {"rows": rows, "current": list(current.values()),
            "source": rows[0]["source"] if rows else ""}


@app.get("/api/dispatch")
def dispatch() -> dict:
    """Best and worst departure time per route (heat-aware dispatch)."""
    return {"suggestions": _read_csv("dispatch_suggestions.csv")}


@app.get("/api/events")
def events(limit: int = 100) -> dict:
    with state.lock:
        return {"events": list(state.events)[:limit]}


@app.get("/api/decisions")
def decisions() -> dict:
    with state.lock:
        return {"decisions": sorted(state.decisions.values(),
                                    key=lambda d: d["created_at"], reverse=True)}


@app.get("/api/decisions/{decision_id}")
def decision(decision_id: str) -> dict:
    with state.lock:
        d = state.decisions.get(decision_id)
    if d is None:
        raise HTTPException(404, f"unknown decision {decision_id}")
    return d


@app.get("/api/audit")
def audit() -> dict:
    ok, broken_at = state.audit.verify()
    return {"records": state.audit.as_list(), "chain_ok": ok, "broken_at": broken_at}


@app.get("/api/impact")
def impact() -> dict:
    """The comparison screen: what happens with and without ColdGuard."""
    with state.lock:
        approved = [d for d in state.decisions.values() if d.get("approved_at")]
    without_kg = sum(d["facts"]["qty_kg"] for d in approved
                     if d["facts"]["if_nothing_done_days"] < d["facts"]["store_minimum_days"])
    with_kg = sum(d["chosen_option"]["kg_saved"] for d in approved)
    value = sum(d["chosen_option"]["score"] for d in approved)
    return {
        "totals": state.totals(),
        "without_coldguard": {"kg_rejected": round(without_kg),
                              "value_lost_qar": round(without_kg * 10),
                              "outcome": "rejected at the gate, sent to landfill"},
        "with_coldguard": {"kg_accepted": round(with_kg),
                           "value_kept_qar": round(value),
                           "co2e_saved_kg": round(with_kg * config.CO2E_PER_KG_FOOD),
                           "outcome": "delivered within the store's freshness minimum"},
        "decisions": approved,
    }


# -------------------------------------------------------------------- write
class ApproveBody(BaseModel):
    chosen: str | None = None
    approved_by: str = "dispatcher"


@app.post("/api/decisions/{decision_id}/approve")
def approve(decision_id: str, body: ApproveBody) -> dict:
    """A human approves; only then does anything change (CLAUDE.md section 3)."""
    with state.lock:
        record = state.decisions.get(decision_id)
        if record is None:
            raise HTTPException(404, f"unknown decision {decision_id}")
        if record.get("approved_at"):
            raise HTTPException(409, "already approved")
        chosen_key = body.chosen or record["recommended"]
        option = next((o for o in record["options"] if o["key"] == chosen_key), None)
        if option is None:
            raise HTTPException(400, f"unknown option {chosen_key}")

        truck = state.trucks[record["truck_id"]]
        _execute(truck, chosen_key, option)

        now = time.time()
        rec = state.audit.append("approve", {
            "decision_id": decision_id, "truck_id": truck.truck_id,
            "chosen": chosen_key, "option": option,
            "approved_by": body.approved_by,
            "evidence": record["facts"]})
        record.update(chosen=chosen_key, chosen_option=option, approved_by=body.approved_by,
                      approved_at=now, prev_hash=rec.prev_hash, hash=rec.hash)
        truck.decision_id = None
        snapshot = truck.as_dict()

    db.approve_decision(decision_id, chosen_key, body.approved_by, now,
                        rec.prev_hash, rec.hash)
    db.upsert_shipment(truck.truck_id, truck.product.product, truck.qty_kg, truck.route_id,
                       truck.override_destination or truck.destination_id, None,
                       truck.life_left_h, truck.status)
    state.bus.publish("decision", record)
    state.bus.publish("reading", snapshot)
    log.info("decision %s approved by %s: option %s", decision_id, body.approved_by, chosen_key)
    return {"ok": True, "decision": record, "truck": snapshot}


def _execute(truck, chosen_key: str, option: dict) -> None:
    """Carry out an approved option. Nothing here moves a real truck."""
    if chosen_key == "A":
        truck.status = "rolling"
        truck.override_destination = None
        truck.reroute_geometry = None
        return
    dest = geo.load_places().get(option["destination_id"])
    truck.override_destination = option["destination_id"]
    truck.status = "donated" if "donate" in option["title_en"].lower() else (
        "sold" if chosen_key == "D" else "rerouted")
    if dest is not None:
        # No router offline: the new leg is drawn as a direct line and labelled.
        truck.reroute_geometry = [[truck.lon, truck.lat], [dest.lon, dest.lat]]


class FaultBody(BaseModel):
    truck_id: str
    fault: str
    on: bool = True


@app.post("/api/demo/fault")
def demo_fault(body: FaultBody) -> dict:
    if body.fault not in ("door", "compressor", "sensor"):
        raise HTTPException(400, "fault must be door, compressor or sensor")
    ok = ingest.publish_control(body.truck_id, {"fault": body.fault, "on": body.on})
    return {"ok": ok, "sent": body.model_dump()}


class BackupBody(BaseModel):
    on: bool = True


@app.post("/api/demo/backup")
def demo_backup(body: BackupBody) -> dict:
    """Hardware fallback: the simulator takes over TRK-07."""
    ok = ingest.publish_control(config.REAL_TRUCK, {"backup": body.on})
    return {"ok": ok, "truck_id": config.REAL_TRUCK, "backup": body.on}


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    ingest.publish_control("all", {"reset": True})
    state.reset()
    db.clear_run_data()
    state.bus.publish("reset", {"at": time.time()})
    log.info("demo reset")
    return {"ok": True}


# ---------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws(socket: WebSocket) -> None:
    await socket.accept()
    queue = state.bus.subscribe()
    try:
        await socket.send_json({"type": "hello",
                                "payload": {"demo_speed": config.DEMO_SPEED,
                                            "map_speed": config.MAP_SPEED,
                                            "real_truck": config.REAL_TRUCK,
                                            "trucks": state.fleet_dicts()},
                                "at": time.time()})
        while True:
            msg = await queue.get()
            await socket.send_json(msg)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        state.bus.unsubscribe(queue)


# ------------------------------------------------------- QR freshness passport
@app.get("/track/{truck_id}", response_class=HTMLResponse)
def track(request: Request, truck_id: str):
    """The page behind the QR code taped to the cooler box."""
    t = state.trucks.get(truck_id)
    if t is None:
        raise HTTPException(404, f"unknown truck {truck_id}")
    with state.lock:
        data = t.as_dict()
        points = list(t.history)[-120:]
        events = [e for e in state.events if e["truck_id"] == truck_id][:8]
    return templates.TemplateResponse(request, "track.html", {
        "truck": data, "points": points, "events": events,
        "points_json": json.dumps([{"ts": p["ts"], "air_c": p["air_c"],
                                    "product_c": p["product_c"]} for p in points]),
        "demo_speed": config.DEMO_SPEED,
    })


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({
        "name": "ColdGuard backend",
        "dashboard": "http://localhost:5173",
        "endpoints": ["/api/fleet", "/api/trucks/{id}/history", "/api/dispatch",
                      "/api/heat", "/api/events", "/api/decisions", "/api/audit",
                      "/api/impact", "/ws", "/track/TRK-07"],
        "demo_speed": config.DEMO_SPEED,
    })
