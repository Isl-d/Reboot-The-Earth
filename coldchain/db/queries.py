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
from datetime import datetime
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

    rows.reverse()
    return [{
        "deviceId": r.device_id,
        "truckId": r.truck_id,
        "timestamp": r.ts.isoformat().replace("+00:00", "Z"),
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
