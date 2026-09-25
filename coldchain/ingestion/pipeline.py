"""The ingest pipeline: the only way telemetry enters the platform.

    raw payload -> validate -> normalize -> derive -> store -> cache -> push

One instance holds the live fleet. Readings arrive on the MQTT thread and the
API serves them from the asyncio loop, so every mutation takes `self.lock`.

Incidents opened here are threshold facts, not predictions: the temperature
has been above the batch's safe maximum for N seconds, the door has been open
too long, cooling is reported off, a shock exceeded the limit. What that means
for the food is Person 4's model.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# Aliased: validation.ValidationError below is a different class
# and would otherwise shadow this one.
from pydantic import ValidationError as PydanticValidationError

from .. import cache, config, fleet
from ..util import camelize
from ..db import models, queries, session as db
from ..schemas import (Derived, DeviceEvent, Incident, Telemetry,
                       TruckState)
from .derived import TruckAccumulator
from .validation import ValidationError, normalize, normalize_event

log = logging.getLogger("coldchain.ingest")

Broadcast = Callable[[dict], None]


class Pipeline:
    def __init__(self, *, broadcast: Optional[Broadcast] = None,
                 persist: bool = True) -> None:
        self.lock = threading.RLock()
        self.trucks: dict[str, TruckState] = {}
        self.accumulators: dict[str, TruckAccumulator] = {}
        self.incidents: dict[str, Incident] = {}
        self.events: list[DeviceEvent] = []
        self.rejected: list[dict] = []
        self._broadcast = broadcast
        self._persist = persist
        self._seq = 0
        self.load_reference()

    # ------------------------------------------------------------- wiring
    def set_broadcast(self, fn: Broadcast) -> None:
        self._broadcast = fn

    def _push(self, message: dict) -> None:
        if self._broadcast is not None:
            try:
                self._broadcast(message)
            except Exception as exc:                  # noqa: BLE001
                log.warning("broadcast failed: %s", exc)

    # --------------------------------------------------------- reference
    def load_reference(self) -> None:
        """Seed the in-memory fleet from the demo world."""
        with self.lock:
            for t in fleet.TRUCKS:
                batch = fleet.batch_for_truck(t["id"])
                product = fleet.product_by_id(batch["product_id"]) if batch else None
                self.trucks[t["id"]] = TruckState(
                    truck_id=t["id"],
                    device_id=fleet.device_id(t["id"]),
                    plate=t["plate"],
                    status="IDLE",
                    batch_id=batch["id"] if batch else None,
                    product=product["name"] if product else None,
                    quantity_kg=batch["quantity_kg"] if batch else None,
                    destination_id=t.get("destination_id"),
                    safe_min_temp_c=batch["safe_min_temp_c"] if batch else None,
                    safe_max_temp_c=batch["safe_max_temp_c"] if batch else None,
                )
                self.accumulators[t["id"]] = TruckAccumulator(t["id"])

    def load_cached_states(self) -> int:
        """Rehydrate the fleet from Redis after a restart.

        This is what the cache is for (spec, section 7): current state lives
        in Redis so it does not have to be rebuilt from the historical table.
        Without it, `GET /api/trucks` reports nulls for every field until the
        next reading arrives — on stage, a blank map for however long that
        takes.

        Only the measured fields are restored. Derived values stay at zero
        because they are accumulations over a stream this process has not
        seen, and reporting a carried-over thermal exposure as if it had been
        observed here would be a fiction.
        """
        restored = 0
        for state in cache.all_latest():
            truck_id = state.get("truckId")
            if not truck_id:
                continue

            with self.lock:
                existing = self.trucks.get(truck_id)
                base = (existing.model_dump(by_alias=True, mode="json")
                        if existing else {"truckId": truck_id})

            # Only the measured fields come back. Everything else — the batch,
            # the safe limits — stays as the reference data defines it.
            merged = dict(base)
            for field in ("deviceId", "latitude", "longitude", "temperatureC",
                          "humidityPct", "speedKmh", "gForce", "doorOpen",
                          "refrigerationOn", "timestamp", "status",
                          "riskScore", "riskLevel"):
                if state.get(field) is not None:
                    merged[field] = state[field]

            # Validate rather than assign. Pydantic does not check assignment,
            # so a corrupt cache entry would otherwise put a string where the
            # dashboard expects a number and break the chart rather than this.
            try:
                truck = TruckState.model_validate(merged)
            except PydanticValidationError as exc:
                log.warning("ignoring unusable cached state for %s: %s",
                            truck_id, exc.error_count())
                continue

            # Derived values are accumulations over a stream this process has
            # not seen, so they start clean instead of being restored as if
            # they had been observed here.
            truck.derived = Derived()

            with self.lock:
                self.trucks[truck_id] = truck
                self.accumulators.setdefault(truck_id, TruckAccumulator(truck_id))
            restored += 1

        if restored:
            log.info("restored %d truck state(s) from the cache", restored)
        return restored

    def load_open_incidents(self, rows: list) -> int:
        """Rehydrate incidents left open by a previous process.

        Without this, a restart mid-demo empties the incident panel while the
        truck is still in trouble, and the next reading opens a duplicate.
        """
        loaded = 0
        with self.lock:
            for r in rows:
                if r.id in self.incidents:
                    continue
                self.incidents[r.id] = Incident(
                    id=r.id, truck_id=r.truck_id, type=r.type,
                    severity=r.severity, status=r.status,
                    opened_at=r.opened_at, closed_at=r.closed_at,
                    detail=r.detail, peak_temperature_c=r.peak_temperature_c)
                loaded += 1
                # Keep the id counter ahead of what is already stored.
                if r.id.startswith("INC-"):
                    try:
                        self._seq = max(self._seq, int(r.id.split("-")[1]))
                    except (IndexError, ValueError):
                        pass
        if loaded:
            log.info("recovered %d open incident(s) from the store", loaded)
        return loaded

    def _destination_latlon(self, truck: TruckState) -> tuple[float, float] | None:
        if not truck.destination_id:
            return None
        place = fleet.place_by_id(truck.destination_id)
        return (place.lat, place.lon) if place else None

    # ------------------------------------------------------------ ingest
    def handle_payload(self, payload: dict[str, Any], *,
                       topic: str | None = None) -> Optional[TruckState]:
        """Entry point for one raw message. Returns the new state, or None."""
        try:
            reading = normalize(payload, topic=topic)
        except ValidationError as exc:
            self._reject(exc, payload)
            return None
        return self.handle_reading(reading)

    def _reject(self, exc: ValidationError, payload: dict) -> None:
        truck_id = str(payload.get("truckId") or payload.get("truck_id") or "UNKNOWN")
        record = {"reason": exc.reason, "detail": exc.detail,
                  "truckId": truck_id,
                  "ts": datetime.now(timezone.utc).isoformat()}
        log.warning("rejected reading from %s - %s", truck_id, exc)
        with self.lock:
            self.rejected.append(record)
            self.rejected[:] = self.rejected[-200:]
        if self._persist:
            self._write_rejection(truck_id, exc, payload)

    def _write_rejection(self, truck_id: str, exc: ValidationError,
                         payload: dict) -> None:
        try:
            with db.session() as s:
                s.add(models.RejectedReading(
                    truck_id=truck_id[:32], reason=exc.reason[:64],
                    detail=exc.detail, payload=json.dumps(payload, default=str)[:4000]))
                s.commit()
        except Exception as e:                        # noqa: BLE001 - demo safety
            log.warning("could not log rejection: %s", e)

    def handle_reading(self, reading: Telemetry) -> TruckState:
        """Fold one validated reading into the fleet."""
        with self.lock:
            truck = self.trucks.get(reading.truck_id)
            if truck is None:
                # A device we have no row for still gets ingested; the fleet
                # table is reference data, not an allowlist.
                truck = TruckState(truck_id=reading.truck_id,
                                   device_id=reading.device_id)
                self.trucks[reading.truck_id] = truck
                self.accumulators[reading.truck_id] = TruckAccumulator(reading.truck_id)

            acc = self.accumulators[reading.truck_id]
            derived = acc.update(reading, safe_max_c=truck.safe_max_temp_c,
                                 destination=self._destination_latlon(truck))

            truck.device_id = reading.device_id
            truck.timestamp = reading.timestamp
            truck.latitude = reading.latitude
            truck.longitude = reading.longitude
            truck.temperature_c = reading.temperature_c
            truck.humidity_pct = reading.humidity_pct
            truck.speed_kmh = reading.speed_kmh
            truck.g_force = reading.g_force
            truck.door_open = reading.door_open
            truck.refrigeration_on = reading.refrigeration_on
            truck.derived = derived
            truck.status = "MOVING" if reading.speed_kmh > 1.0 else "STOPPED"

            risk = cache.get_risk(reading.truck_id)
            if risk:
                truck.risk_score = risk.get("riskScore")
                truck.risk_level = risk.get("riskLevel") or "UNKNOWN"

            state = truck.model_dump(by_alias=True, mode="json")
            new_incidents = self._check_incidents(truck, acc, reading)

        if self._persist:
            self._store(reading)
        cache.set_latest(reading.truck_id, state)

        self._push({"event": "TRUCK_STATE_UPDATED", **state})
        for inc in new_incidents:
            self._push({"event": "INCIDENT_CREATED",
                        **inc.model_dump(by_alias=True, mode="json")})
        return truck

    def _store(self, r: Telemetry) -> None:
        try:
            with db.session() as s:
                s.add(models.SensorReading(
                    ts=r.timestamp, truck_id=r.truck_id, device_id=r.device_id,
                    temperature_c=r.temperature_c, humidity_pct=r.humidity_pct,
                    latitude=r.latitude, longitude=r.longitude,
                    speed_kmh=r.speed_kmh, g_force=r.g_force,
                    door_open=r.door_open, refrigeration_on=r.refrigeration_on))
                s.commit()
        except Exception as exc:                      # noqa: BLE001 - demo safety
            log.warning("could not store reading: %s", exc)

    # ----------------------------------------------------- device events
    def handle_event_payload(self, payload: dict[str, Any], *,
                             topic: str | None = None) -> Optional[DeviceEvent]:
        """Entry point for one raw message on the events topic."""
        try:
            event = normalize_event(payload, topic=topic)
        except ValidationError as exc:
            self._reject(exc, payload)
            return None
        return self.handle_event(event)

    def handle_event(self, event: DeviceEvent) -> DeviceEvent:
        """Record a device event and reflect what it says about the truck.

        A door opening reported the instant it happens keeps the dashboard
        current between telemetry ticks. The next reading carries the same
        field and simply overwrites it, so telemetry stays authoritative.

        Incident thresholds are deliberately not driven from here: they are
        accumulated from the telemetry stream, whose timestamps are regular.
        An event only says a thing happened, not for how long.
        """
        with self.lock:
            truck = self.trucks.get(event.truck_id)
            if truck is None:
                truck = TruckState(truck_id=event.truck_id,
                                   device_id=event.device_id)
                self.trucks[event.truck_id] = truck
                self.accumulators[event.truck_id] = TruckAccumulator(event.truck_id)

            if event.type == "DOOR_OPENED":
                truck.door_open = True
            elif event.type == "DOOR_CLOSED":
                truck.door_open = False
            elif event.type == "REFRIGERATION_ON":
                truck.refrigeration_on = True
            elif event.type == "REFRIGERATION_OFF":
                truck.refrigeration_on = False

            self.events.append(event)
            self.events[:] = self.events[-config.WINDOW_SIZE:]
            state = truck.model_dump(by_alias=True, mode="json")

        if self._persist:
            self._store_event(event)
        cache.set_latest(event.truck_id, state)

        self._push({"event": "DEVICE_EVENT",
                    **event.model_dump(by_alias=True, mode="json")})
        self._push({"event": "TRUCK_STATE_UPDATED", **state})
        return event

    def _store_event(self, e: DeviceEvent) -> None:
        try:
            with db.session() as s:
                s.add(models.DeviceEventRow(
                    ts=e.timestamp, truck_id=e.truck_id, device_id=e.device_id,
                    type=e.type, detail=e.detail, value=e.value))
                s.commit()
        except Exception as exc:                      # noqa: BLE001 - demo safety
            log.warning("could not store device event: %s", exc)

    def device_events(self, truck_id: str | None = None,
                      limit: int = 100) -> list[DeviceEvent]:
        with self.lock:
            rows = [e for e in self.events
                    if truck_id is None or e.truck_id == truck_id]
            return rows[-limit:]

    # --------------------------------------------------------- incidents
    def _open(self, truck_id: str, kind: str, severity: str, detail: str,
              peak: float | None, at: datetime, *,
              instantaneous: bool = False) -> Optional[Incident]:
        """Open an incident unless one of this kind is already open.

        An instantaneous incident - a shock is over the moment it happens -
        skips the dedupe and is recorded closed, otherwise the first one would
        stay OPEN forever and every later shock would be swallowed as a
        duplicate of it.
        """
        if not instantaneous:
            for inc in self.incidents.values():
                if (inc.truck_id == truck_id and inc.type == kind
                        and inc.status == "OPEN"):
                    if peak is not None and peak > (inc.peak_temperature_c or peak - 1):
                        inc.peak_temperature_c = peak
                        # Persist and push, or a restart recovers a stale peak.
                        if self._persist:
                            self._write_incident(inc)
                        self._push({"event": "INCIDENT_UPDATED",
                                    **inc.model_dump(by_alias=True, mode="json")})
                    return None
        self._seq += 1
        inc = Incident(id=f"INC-{self._seq:04d}", truck_id=truck_id, type=kind,
                       severity=severity,
                       status="CLOSED" if instantaneous else "OPEN",
                       opened_at=at, closed_at=at if instantaneous else None,
                       detail=detail, peak_temperature_c=peak)
        self.incidents[inc.id] = inc
        log.info("incident %s %s on %s - %s", inc.id, kind, truck_id, detail)
        if self._persist:
            self._write_incident(inc)
        return inc

    def _close(self, truck_id: str, kind: str, at: datetime) -> None:
        for inc in self.incidents.values():
            if inc.truck_id == truck_id and inc.type == kind and inc.status == "OPEN":
                inc.status = "CLOSED"
                inc.closed_at = at
                if self._persist:
                    self._write_incident(inc)
                self._push({"event": "INCIDENT_UPDATED",
                            **inc.model_dump(by_alias=True, mode="json")})

    def _write_incident(self, inc: Incident) -> None:
        try:
            with db.session() as s:
                s.merge(models.IncidentRow(
                    id=inc.id, truck_id=inc.truck_id, type=inc.type,
                    severity=inc.severity, status=inc.status,
                    opened_at=inc.opened_at, closed_at=inc.closed_at,
                    detail=inc.detail, peak_temperature_c=inc.peak_temperature_c))
                s.commit()
        except Exception as exc:                      # noqa: BLE001
            log.warning("could not store incident: %s", exc)

    def _check_incidents(self, truck: TruckState, acc: TruckAccumulator,
                         r: Telemetry) -> list[Incident]:
        """Threshold facts only. No prediction, no spoilage estimate."""
        opened: list[Incident] = []
        now = r.timestamp
        safe_max = truck.safe_max_temp_c

        run = acc.current_excursion_run_s(safe_max)
        if safe_max is not None and run >= config.EXCURSION_INCIDENT_S:
            inc = self._open(
                r.truck_id, "TEMPERATURE_EXCURSION", "CRITICAL",
                f"{r.temperature_c:.1f} C is above the {safe_max:.0f} C limit "
                f"and has been for {run:.0f}s",
                acc.peak_temperature_c(), now)
            if inc:
                opened.append(inc)
        elif safe_max is not None and r.temperature_c <= safe_max:
            self._close(r.truck_id, "TEMPERATURE_EXCURSION", now)

        door_run = acc.current_door_run_s(now)
        if door_run >= config.DOOR_OPEN_INCIDENT_S:
            inc = self._open(r.truck_id, "DOOR_LEFT_OPEN", "HIGH",
                             f"door has been open for {door_run:.0f}s", None, now)
            if inc:
                opened.append(inc)
        elif not r.door_open:
            self._close(r.truck_id, "DOOR_LEFT_OPEN", now)

        fridge_run = acc.current_refrigeration_off_run_s(now)
        if fridge_run >= config.REFRIGERATION_INCIDENT_S:
            inc = self._open(r.truck_id, "REFRIGERATION_FAILURE", "CRITICAL",
                             f"refrigeration has been off for {fridge_run:.0f}s",
                             acc.peak_temperature_c(), now)
            if inc:
                opened.append(inc)
        elif r.refrigeration_on:
            self._close(r.truck_id, "REFRIGERATION_FAILURE", now)

        if r.g_force >= config.GFORCE_INCIDENT:
            inc = self._open(r.truck_id, "SHOCK", "MEDIUM",
                             f"shock of {r.g_force:.1f} g recorded", None, now,
                             instantaneous=True)
            if inc:
                opened.append(inc)

        return opened

    # ----------------------------------------------- person 4 integration
    def context_for(self, truck_id: str, *, limit: int = 60) -> Optional[dict]:
        """The normalized bundle Person 4's model consumes."""
        with self.lock:
            truck = self.trucks.get(truck_id)
            if truck is None:
                return None
            acc = self.accumulators[truck_id]
            batch = fleet.batch_for_truck(truck_id)
            recent = [t.model_dump(by_alias=True, mode="json")
                      for t in acc.recent(limit)]
        return {
            "truck": truck.model_dump(by_alias=True, mode="json"),
            "batch": camelize(batch),
            "recentTelemetry": recent,
            # Live capacity: Person 4 picks a destination from this, and
            # available space changes as stock moves.
            "candidateWarehouses": queries.warehouses()[0],
        }

    def apply_prediction(self, p: dict) -> Optional[TruckState]:
        """Store what Person 4 returns and forward it to the frontend."""
        truck_id = p.get("truckId") or p.get("truck_id")
        if not truck_id:
            return None
        with self.lock:
            truck = self.trucks.get(truck_id)
            if truck is None:
                return None
            if p.get("riskScore") is not None:
                truck.risk_score = p["riskScore"]
            if p.get("riskLevel"):
                truck.risk_level = p["riskLevel"]
            state = truck.model_dump(by_alias=True, mode="json")
        cache.set_risk(truck_id, {"riskScore": truck.risk_score,
                                  "riskLevel": truck.risk_level,
                                  **{k: v for k, v in p.items()
                                     if k not in ("truckId", "truck_id")}})
        cache.set_latest(truck_id, state)
        self._push({"event": "PREDICTION_UPDATED", **p})
        self._push({"event": "TRUCK_STATE_UPDATED", **state})
        return truck

    # -------------------------------------------------------------- views
    def fleet_states(self) -> list[TruckState]:
        with self.lock:
            return sorted(self.trucks.values(), key=lambda t: t.truck_id)

    def telemetry(self, truck_id: str, limit: int = 200) -> list[Telemetry]:
        with self.lock:
            acc = self.accumulators.get(truck_id)
            return acc.recent(limit) if acc else []

    def open_incidents(self) -> list[Incident]:
        with self.lock:
            return [i for i in self.incidents.values() if i.status == "OPEN"]

    def all_incidents(self) -> list[Incident]:
        with self.lock:
            return sorted(self.incidents.values(), key=lambda i: i.opened_at,
                          reverse=True)

    def reset(self) -> None:
        with self.lock:
            self.incidents.clear()
            self.events.clear()
            self.rejected.clear()
            self._seq = 0
            for acc in self.accumulators.values():
                acc.reset()
            self.trucks.clear()
            self.accumulators.clear()
            self.load_reference()
        cache.clear()
        self._push({"event": "SIMULATION_RESET"})
