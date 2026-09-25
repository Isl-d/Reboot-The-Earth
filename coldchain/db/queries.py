"""Reads against the historical store.

The in-memory window in the pipeline is a live buffer: it holds the last
`WINDOW_SIZE` readings and it is gone when the process restarts. Person 2's
charts need more than that, so history comes from `sensor_readings`, which is
the authoritative record.

Every function here degrades to an empty result rather than raising: losing
the database mid-demo must not take the API down.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select

from . import models, session as db

log = logging.getLogger("coldchain.queries")


def readings(truck_id: str, *, limit: int = 200,
             since: datetime | None = None) -> list[dict[str, Any]]:
    """Recent readings for one truck, oldest first (chart order)."""
    try:
        with db.session() as s:
            stmt = select(models.SensorReading).where(
                models.SensorReading.truck_id == truck_id)
            if since is not None:
                stmt = stmt.where(models.SensorReading.ts >= since)
            stmt = stmt.order_by(desc(models.SensorReading.ts)).limit(limit)
            rows = list(s.execute(stmt).scalars())
    except Exception as exc:                          # noqa: BLE001 - demo safety
        log.warning("history query failed (%s) - falling back to memory", exc)
        return []

    def _utc(ts):
        # SQLite hands back naive datetimes. Emitting one without a "Z" makes
        # a browser read it as local time, so REST history and the WebSocket
        # would disagree by the viewer's offset.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    rows.reverse()
    return [{
        "deviceId": r.device_id,
        "truckId": r.truck_id,
        "timestamp": _utc(r.ts),
        "temperatureC": r.temperature_c,
        "humidityPct": r.humidity_pct,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "speedKmh": r.speed_kmh,
        "gForce": r.g_force,
        "doorOpen": r.door_open,
        "refrigerationOn": r.refrigeration_on,
    } for r in rows]


def reading_count(truck_id: str) -> int:
    from sqlalchemy import func

    try:
        with db.session() as s:
            return int(s.execute(
                select(func.count()).select_from(models.SensorReading)
                .where(models.SensorReading.truck_id == truck_id)).scalar() or 0)
    except Exception:                                 # noqa: BLE001
        return 0


def open_incidents() -> list[models.IncidentRow]:
    """Incidents still open in the store, so a restart does not lose them."""
    try:
        with db.session() as s:
            return list(s.execute(
                select(models.IncidentRow)
                .where(models.IncidentRow.status == "OPEN")
                .order_by(desc(models.IncidentRow.opened_at))).scalars())
    except Exception as exc:                          # noqa: BLE001
        log.warning("could not load open incidents (%s)", exc)
        return []


def start_run(scenario: str, speed_multiplier: float, seed: int) -> int | None:
    """Record a simulation run. Returns its id, or None if the store is down."""
    try:
        with db.session() as s:
            row = models.SimulationRun(scenario=scenario,
                                       speed_multiplier=speed_multiplier,
                                       seed=seed)
            s.add(row)
            s.commit()
            return row.id
    except Exception as exc:                          # noqa: BLE001
        log.warning("could not record simulation run (%s)", exc)
        return None


def stop_run(run_id: int | None, when: datetime) -> None:
    if run_id is None:
        return
    try:
        with db.session() as s:
            row = s.get(models.SimulationRun, run_id)
            if row is not None and row.stopped_at is None:
                row.stopped_at = when
                s.commit()
    except Exception as exc:                          # noqa: BLE001
        log.warning("could not close simulation run (%s)", exc)


def close_stale_runs() -> int:
    """Close runs left open by a process that died without stopping.

    Stamping them with `now` would inflate the duration by however long the
    service was down, so they are closed at the last evidence the run was
    alive: the newest reading in the store.
    """
    from sqlalchemy import func

    try:
        with db.session() as s:
            open_runs = list(s.execute(
                select(models.SimulationRun)
                .where(models.SimulationRun.stopped_at.is_(None))).scalars())
            if not open_runs:
                return 0
            last = s.execute(select(func.max(models.SensorReading.ts))).scalar()
            for row in open_runs:
                row.stopped_at = last or row.started_at
            s.commit()
            log.info("closed %d simulation run(s) left open by a previous process",
                     len(open_runs))
            return len(open_runs)
    except Exception as exc:                          # noqa: BLE001
        log.warning("could not close stale runs (%s)", exc)
        return 0


def runs(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with db.session() as s:
            rows = list(s.execute(
                select(models.SimulationRun)
                .order_by(desc(models.SimulationRun.started_at))
                .limit(limit)).scalars())
    except Exception:                                 # noqa: BLE001
        return []
    return [{
        "id": r.id,
        "startedAt": r.started_at.isoformat() if r.started_at else None,
        "stoppedAt": r.stopped_at.isoformat() if r.stopped_at else None,
        "scenario": r.scenario,
        "speedMultiplier": r.speed_multiplier,
        "seed": r.seed,
    } for r in rows]


# ------------------------------------------------------- reference data
#
# These tables are seeded from fleet.py, but once seeded the database is the
# authoritative copy: a warehouse's available capacity changes as stock moves,
# and Person 4 picks a destination from it. Serving the hard-coded constants
# instead would mean that column could never change.
#
# Each falls back to fleet.py when the store is empty or unreachable, so the
# API still answers on a laptop with no database.

def _rows(model, to_dict, fallback):
    try:
        with db.session() as s:
            rows = list(s.execute(select(model)).scalars())
    except Exception as exc:                          # noqa: BLE001 - demo safety
        log.warning("reference query failed (%s) - serving fleet.py", exc)
        return fallback(), "fallback"
    if not rows:
        return fallback(), "fallback"
    return [to_dict(r) for r in rows], "database"


def _warehouse(r) -> dict[str, Any]:
    return {"id": r.id, "name": r.name, "latitude": r.latitude,
            "longitude": r.longitude, "capacityKg": r.capacity_kg,
            "availableCapacityKg": r.available_capacity_kg,
            "minTempC": r.min_temp_c, "maxTempC": r.max_temp_c}


def _store(r) -> dict[str, Any]:
    return {"id": r.id, "name": r.name, "latitude": r.latitude,
            "longitude": r.longitude}


def _batch(r) -> dict[str, Any]:
    return {"id": r.id, "productId": r.product_id, "quantityKg": r.quantity_kg,
            "productionDate": r.production_date, "expiryDate": r.expiry_date,
            "safeMinTempC": r.safe_min_temp_c, "safeMaxTempC": r.safe_max_temp_c,
            "initialShelfLifeHours": r.initial_shelf_life_hours,
            "truckId": r.truck_id}


def warehouses() -> tuple[list[dict[str, Any]], str]:
    from .. import fleet
    from ..util import camelize

    return _rows(models.Warehouse, _warehouse,
                 lambda: camelize(fleet.WAREHOUSES))


def stores() -> tuple[list[dict[str, Any]], str]:
    from .. import fleet
    from ..util import camelize

    return _rows(models.Store, _store, lambda: camelize(fleet.STORES))


def batches() -> tuple[list[dict[str, Any]], str]:
    from .. import fleet
    from ..util import camelize

    return _rows(models.ProductBatch, _batch, lambda: camelize(fleet.BATCHES))


def warehouse(warehouse_id: str) -> dict[str, Any] | None:
    rows, _ = warehouses()
    return next((w for w in rows if w["id"] == warehouse_id), None)


def batch(batch_id: str) -> dict[str, Any] | None:
    rows, _ = batches()
    return next((b for b in rows if b["id"] == batch_id), None)


def clear_stream_tables() -> dict[str, int]:
    """Empty the per-run tables on POST /api/simulation/reset.

    Resetting rewinds the simulated clock to now, so readings written before
    it carry timestamps in the future. `readings()` takes the newest rows by
    ts, which means the chart would keep serving those stale rows and appear
    frozen. Reference data is untouched.
    """
    from sqlalchemy import delete

    counts: dict[str, int] = {}
    try:
        with db.session() as s:
            for name, model in (("sensor_readings", models.SensorReading),
                                ("device_events", models.DeviceEventRow),
                                ("incidents", models.IncidentRow),
                                ("rejected_readings", models.RejectedReading)):
                counts[name] = s.execute(delete(model)).rowcount or 0
            s.commit()
        log.info("reset cleared %s", counts)
    except Exception as exc:                          # noqa: BLE001 - demo safety
        log.warning("could not clear stream tables (%s)", exc)
    return counts
