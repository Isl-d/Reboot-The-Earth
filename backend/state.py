"""In-memory fleet state: the thing the dashboard actually reads.

One process, one dictionary of trucks. PostgreSQL is the durable copy; this is
the live one. Telemetry arrives on the MQTT thread and the API serves it from
the asyncio loop, so every mutation goes through `FleetState.lock`.
"""
from __future__ import annotations

import asyncio
import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from . import config, freshness, geo
from .audit import AuditLog
from .detector import FAILURE, SENSOR_FAULT, TruckDetector
from .freshness import Product


@dataclass
class TruckState:
    """Everything known about one shipment right now."""

    truck_id: str
    route_id: str
    product: Product
    qty_kg: float
    start_frac: float
    frac: float = 0.0
    lat: float = 0.0
    lon: float = 0.0
    air_c: float | None = None
    product_c: float | None = None
    hum_pct: float | None = None
    door_open: bool = False
    src: str = "sim"
    last_ts: float | None = None
    life_left_h: float = 0.0
    status: str = "rolling"
    destination_id: str = ""
    override_destination: str | None = None
    reroute_geometry: list[list[float]] | None = None
    decision_id: str | None = None
    detector: TruckDetector = field(init=False)
    history: deque = field(default_factory=lambda: deque(maxlen=config.HISTORY_POINTS))

    def __post_init__(self) -> None:
        self.detector = TruckDetector(self.truck_id, self.product)
        self.reset()

    # ------------------------------------------------------------------ life
    def reset(self) -> None:
        route = geo.load_routes()[self.route_id]
        self.frac = self.start_frac
        self.lat, self.lon = route.point_at(self.frac)
        self.air_c = self.product_c = self.hum_pct = None
        self.door_open = False
        self.last_ts = None
        self.life_left_h = self.product.life_at_ideal_h * config.START_LIFE_FRACTION
        self.status = "rolling"
        self.destination_id = route.destination_id
        self.override_destination = None
        self.reroute_geometry = None
        self.decision_id = None
        self.detector = TruckDetector(self.truck_id, self.product)
        self.history.clear()

    @property
    def route(self) -> geo.Route:
        return geo.load_routes()[self.route_id]

    @property
    def is_live_sensor(self) -> bool:
        return self.src == "esp8266"

    # ------------------------------------------------------------- readings
    def apply(self, reading: dict[str, Any]) -> float:
        """Update position, temperature and shelf life. Returns dt in seconds."""
        ts = reading["ts"]
        dt_s = 0.0 if self.last_ts is None else max(0.0, ts - self.last_ts)
        self.air_c = reading.get("air_c")
        self.hum_pct = reading.get("hum_pct")
        if isinstance(self.air_c, (int, float)) and self.detector.sensor_ok:
            if self.product_c is None:
                self.product_c = self.air_c
            elif dt_s:
                # First-order lag on the demo clock: the pallet warms slowly.
                tau_s = max(config.PRODUCT_LAG_H * 3600.0, 1.0)
                self.product_c += (self.air_c - self.product_c) * (
                    1.0 - math.exp(-dt_s * config.DEMO_SPEED / tau_s))
        self.door_open = bool(reading.get("door_open", False))
        self.src = reading.get("src", self.src)

        if reading.get("lat") is not None and reading.get("lon") is not None:
            self.lat, self.lon = reading["lat"], reading["lon"]
            if dt_s:
                self.frac = self.route.frac_of_nearest_point(self.lat, self.lon)
        else:
            # The NodeMCU only sends temperature, so the backend supplies the
            # position: it moves TRK-07 along its route on the demo clock.
            if self.status not in self.STOPPED:
                route_s = max(self.route.duration_min, 1.0) * 60.0
                self.frac = min(1.0, self.frac + dt_s * config.MAP_SPEED / route_s)
                self.lat, self.lon = self.route.point_at(self.frac)

        # Shelf life only ticks while the sensor is trusted (section 7.2), and
        # it is driven by the product temperature, not the air reading.
        if (dt_s and self.detector.sensor_ok and self.status not in self.OFF_ROAD
                and isinstance(self.product_c, (int, float))):
            self.life_left_h = freshness.advance(self.life_left_h, dt_s, self.product_c,
                                                 self.product)

        self.last_ts = ts
        self.history.append({"ts": ts, "air_c": self.air_c,
                             "product_c": None if self.product_c is None else round(self.product_c, 2),
                             "hum_pct": self.hum_pct,
                             "life_left_h": round(self.life_left_h, 2),
                             "life_on_arrival_h": round(self.life_on_arrival_h, 2)})
        return dt_s

    # ------------------------------------------------------------- derived
    @property
    def aging_speed(self) -> float:
        """How many times faster than ideal the cargo is ageing right now."""
        if not isinstance(self.product_c, (int, float)) or not self.detector.sensor_ok:
            return 1.0
        return freshness.aging_speed(self.product_c, self.product)

    # Statuses: rolling (on the planned route), rerouted (a decision has been
    # approved), sold / donated (off the road, the clock stops).
    OFF_ROAD = ("sold", "donated", "delivered")     # the shelf-life clock stops
    STOPPED = ("sold", "donated", "delivered", "held")   # the truck stops moving

    @property
    def destination(self) -> geo.Place | None:
        return geo.load_places().get(self.override_destination or self.destination_id)

    @property
    def remaining_trip_h(self) -> float:
        """Hours until the food is on a shelf, including handling at the node."""
        if self.status in self.OFF_ROAD:
            return 0.0
        dest = self.destination
        if self.override_destination and dest is not None:
            km = geo.haversine_km(self.lat, self.lon, dest.lat, dest.lon) * config.ROAD_FACTOR
            drive_h = geo.drive_h(km)
        else:
            drive_h = self.route.remaining_h(self.frac)
        if dest is not None and dest.type in ("store", "food_bank"):
            return drive_h + config.HANDOVER_STORE_H
        return drive_h + config.HANDOVER_WAREHOUSE_H

    @property
    def life_on_arrival_h(self) -> float:
        """Shelf life left when the load reaches the shelf.

        While the detector has a cooling failure open, the projection is the
        worst case: nobody fixes it, the load stays warm the whole way. Short
        warm spells (a door opening) are assumed to be over within
        WARM_PROJECTION_H, so a lifted lid never turns the fleet amber.
        """
        speed = self.aging_speed
        remaining = self.remaining_trip_h
        warm_h = remaining if self.detector.has(FAILURE) else min(remaining,
                                                                  config.WARM_PROJECTION_H)
        left = freshness.life_on_arrival_h(self.life_left_h, warm_h, speed)
        return freshness.life_on_arrival_h(left, remaining - warm_h, 1.0)

    @property
    def risk(self) -> str:
        if self.detector.has(SENSOR_FAULT):
            return "unknown"
        return freshness.risk_level(self.life_on_arrival_h, self.product)

    @property
    def destination_name(self) -> str:
        pl = geo.load_places().get(self.override_destination or self.destination_id)
        return pl.name if pl else (self.override_destination or self.destination_id)

    def as_dict(self) -> dict:
        return {
            "truck_id": self.truck_id,
            "route_id": self.route_id,
            "route_name": self.route.name,
            "product": self.product.product,
            "qty_kg": self.qty_kg,
            "lat": round(self.lat, 5),
            "lon": round(self.lon, 5),
            "frac": round(self.frac, 4),
            "air_c": self.air_c,
            "product_c": None if self.product_c is None else round(self.product_c, 2),
            "hum_pct": self.hum_pct,
            "door_open": self.door_open,
            "src": self.src,
            "live_sensor": self.is_live_sensor,
            "last_ts": self.last_ts,
            "online": self.last_ts is not None and time.time() - self.last_ts < config.SENSOR_GAP_S,
            "alert_limit_c": self.product.alert_limit_c,
            "ideal_temp_c": self.product.ideal_temp_c,
            "life_left_h": round(self.life_left_h, 2),
            "life_left_days": round(self.life_left_h / 24.0, 2),
            "freshness_pct": round(freshness.freshness_pct(self.life_left_h, self.product), 1),
            "aging_speed": round(self.aging_speed, 2),
            "hours_to_spoil": round(freshness.hours_to_spoil(
                self.life_left_h, self.product_c if isinstance(self.product_c, (int, float))
                else self.product.ideal_temp_c, self.product), 1),
            "remaining_trip_h": round(self.remaining_trip_h, 2),
            "life_on_arrival_h": round(self.life_on_arrival_h, 2),
            "life_on_arrival_days": round(self.life_on_arrival_h / 24.0, 2),
            "min_life_on_arrival_days": self.product.min_life_on_arrival_days,
            "at_risk": freshness.at_risk(self.life_on_arrival_h, self.product),
            "risk": self.risk,
            "status": self.status,
            "destination_id": self.override_destination or self.destination_id,
            "destination_name": self.destination_name,
            "reroute_geometry": self.reroute_geometry,
            "sensor_ok": self.detector.sensor_ok,
            "in_failure": self.detector.has(FAILURE),
            "decision_id": self.decision_id,
        }


class Broadcaster:
    """Fan-out of WebSocket messages, safe to call from the MQTT thread."""

    def __init__(self) -> None:
        self._queues: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        with self._lock:
            self._queues.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._queues.discard(q)

    def publish(self, kind: str, payload: Any) -> None:
        msg = {"type": kind, "payload": payload, "at": time.time()}
        with self._lock:
            queues = list(self._queues)
        if self._loop is None:
            return
        for q in queues:
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, msg)
            except (RuntimeError, asyncio.QueueFull):
                pass


class FleetState:
    """The whole demo world in one object."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.trucks: dict[str, TruckState] = {}
        self.events: deque = deque(maxlen=400)
        self.decisions: dict[str, dict] = {}
        self.audit = AuditLog()
        self.bus = Broadcaster()
        self.started_at = time.time()
        self._decision_seq = 0
        self.build()

    def build(self) -> None:
        import sys
        sys.path.insert(0, str(config.ROOT / "scripts"))
        from places import FLEET                       # noqa: E402

        with self.lock:
            self.trucks = {
                tid: TruckState(truck_id=tid, route_id=route, qty_kg=qty,
                                product=freshness.get_product(product), start_frac=start,
                                src="esp8266" if tid == config.REAL_TRUCK else "sim")
                for tid, route, product, qty, start in FLEET
            }

    def reset(self) -> None:
        with self.lock:
            for t in self.trucks.values():
                t.reset()
            self.events.clear()
            self.decisions.clear()
            self.audit.reset()
            self.started_at = time.time()
            self._decision_seq = 0

    def next_decision_id(self) -> str:
        with self.lock:
            self._decision_seq += 1
            return f"DEC-{self._decision_seq:04d}"

    def fleet_dicts(self) -> list[dict]:
        with self.lock:
            return [t.as_dict() for t in self.trucks.values()]

    def totals(self) -> dict:
        """Headline numbers for the comparison screen."""
        with self.lock:
            trucks = list(self.trucks.values())
            approved = [d for d in self.decisions.values() if d.get("approved_at")]
        kg_at_risk = sum(t.qty_kg for t in trucks
                         if freshness.at_risk(t.life_on_arrival_h, t.product))
        kg_saved = sum(d["chosen_option"]["kg_saved"] for d in approved)
        value_saved = sum(d["chosen_option"]["score"] for d in approved)
        return {
            "trucks": len(trucks),
            "kg_monitored": round(sum(t.qty_kg for t in trucks)),
            "kg_at_risk": round(kg_at_risk),
            "kg_saved": round(kg_saved),
            "value_saved_qar": round(value_saved),
            "co2e_saved_kg": round(kg_saved * config.CO2E_PER_KG_FOOD),
            "decisions": len(self.decisions),
            "approved": len(approved),
            "audit_ok": self.audit.verify()[0],
            "demo_speed": config.DEMO_SPEED,
        }


state = FleetState()
