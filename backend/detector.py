"""Cold-chain anomaly detector (CLAUDE.md section 7.2).

Tells four things apart, per truck, from the raw temperature stream:

| Event        | Rule (demo value / real-world value)                            | Result                  |
| ------------ | --------------------------------------------------------------- | ----------------------- |
| door         | `door_open` true, or a rise that returns below the alert limit   | log, no action          |
|              | within 20 s / 10 min                                             |                         |
| defrost      | small bump (< 2 C) that recovers on its own                      | log only                |
| sensor_fault | -127, NaN, no reading for 10 s, or a jump > 15 C                 | warn, pause freshness   |
| failure      | above the alert limit for 30-45 s / 10 min, door closed, and the | ALERT -> planner        |
|              | temperature is rising or flat                                    |                         |

Everything is deterministic and driven by the thresholds in config.py, so the
same trace always produces the same events.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

from . import config
from .freshness import Product

DOOR = "door"
DEFROST = "defrost"
SENSOR_FAULT = "sensor_fault"
FAILURE = "failure"

_NOTES = {
    DOOR: "Door opening - no action",
    DEFROST: "Defrost cycle - no action",
    SENSOR_FAULT: "Check sensor - freshness paused",
    FAILURE: "Cooling failure - shipment at risk",
}


@dataclass
class Event:
    """One detected episode. `ended_at` is None while it is still running."""

    truck_id: str
    type: str
    started_at: float
    ended_at: float | None = None
    peak_c: float | None = None
    note: str = ""
    alert: bool = False
    seq: int = 0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = None if self.ended_at is None else round(self.ended_at - self.started_at, 1)
        return d


def _is_bad_reading(air_c: float | None) -> bool:
    if air_c is None:
        return True
    if isinstance(air_c, float) and math.isnan(air_c):
        return True
    return air_c <= config.SENSOR_SENTINEL_C + 1.0 or air_c > 120.0


@dataclass
class TruckDetector:
    """Rolling state for one truck. Feed it every reading in order."""

    truck_id: str
    product: Product
    _seq: int = 0
    last_ts: float | None = None
    last_air: float | None = None
    sensor_ok: bool = True
    _open: dict[str, Event] = field(default_factory=dict)
    _excursion_saw_door: bool = False
    _baseline: float | None = None

    # ---------------------------------------------------------------- helpers
    def _start(self, kind: str, ts: float, air_c: float | None, alert: bool = False) -> Event:
        self._seq += 1
        ev = Event(truck_id=self.truck_id, type=kind, started_at=ts, peak_c=air_c,
                   note=_NOTES[kind], alert=alert, seq=self._seq)
        self._open[kind] = ev
        return ev

    def _close(self, kind: str, ts: float) -> Event | None:
        ev = self._open.pop(kind, None)
        if ev is not None:
            ev.ended_at = ts
        return ev

    @property
    def active(self) -> list[Event]:
        return list(self._open.values())

    def has(self, kind: str) -> bool:
        return kind in self._open

    # ------------------------------------------------------------------ input
    def check_timeout(self, now: float) -> list[Event]:
        """Call on a timer: a truck that went silent has a sensor fault too."""
        if self.last_ts is None or self.has(SENSOR_FAULT):
            return []
        if now - self.last_ts > config.SENSOR_GAP_S:
            self.sensor_ok = False
            return [self._start(SENSOR_FAULT, now, self.last_air)]
        return []

    def update(self, ts: float, air_c: float | None, door_open: bool = False) -> list[Event]:
        """Feed one reading. Returns the events that started or ended right now."""
        out: list[Event] = []
        gap = None if self.last_ts is None else ts - self.last_ts

        # 1. sensor health ------------------------------------------------
        bad = _is_bad_reading(air_c)
        jump = (not bad and self.last_air is not None and self.sensor_ok
                and abs(air_c - self.last_air) > config.SENSOR_JUMP_C)
        silent = gap is not None and gap > config.SENSOR_GAP_S
        if bad or jump or silent:
            self.sensor_ok = False
            if not self.has(SENSOR_FAULT):
                out.append(self._start(SENSOR_FAULT, ts, None if bad else air_c))
            self.last_ts = ts
            if not bad:
                self.last_air = air_c
            return out
        if self.has(SENSOR_FAULT):
            ev = self._close(SENSOR_FAULT, ts)
            if ev:
                out.append(ev)
        self.sensor_ok = True

        limit = self.product.alert_limit_c
        setpoint = self.product.ideal_temp_c

        # 2. physical door switch (optional lid switch on the demo box) ----
        if door_open and not self.has(DOOR):
            out.append(self._start(DOOR, ts, air_c))
        if self.has(DOOR):
            ev = self._open[DOOR]
            ev.peak_c = max(ev.peak_c or air_c, air_c)
            if not door_open and air_c <= limit:
                out.append(self._close(DOOR, ts))

        # 3. excursion above the product's alert limit ---------------------
        if air_c > limit:
            # Whatever this is, it is not a defrost cycle any more.
            self._open.pop(DEFROST, None)
            if "_exc" not in self._open:
                self._seq += 1
                self._open["_exc"] = Event(truck_id=self.truck_id, type="_exc",
                                           started_at=ts, peak_c=air_c, seq=self._seq)
                self._excursion_saw_door = door_open
            exc = self._open["_exc"]
            exc.peak_c = max(exc.peak_c or air_c, air_c)
            self._excursion_saw_door = self._excursion_saw_door or door_open
            held = ts - exc.started_at
            rising_or_flat = (self.last_air is None or gap in (None, 0)
                              or (air_c - self.last_air) / max(gap, 1e-9) > -config.FAILURE_MAX_FALL_C_PER_S)
            if (held >= config.FAILURE_HOLD_S and not door_open
                    and not self._excursion_saw_door and rising_or_flat
                    and not self.has(FAILURE)):
                ev = self._start(FAILURE, exc.started_at, exc.peak_c, alert=True)
                out.append(ev)
            if self.has(FAILURE):
                self._open[FAILURE].peak_c = max(self._open[FAILURE].peak_c or air_c, air_c)
        else:
            exc = self._open.pop("_exc", None)
            if exc is not None and not self.has(FAILURE):
                # Came back under the limit on its own.
                kind = DOOR if (self._excursion_saw_door
                                or ts - exc.started_at <= config.DOOR_WINDOW_S) else DEFROST
                self._seq += 1
                out.append(Event(truck_id=self.truck_id, type=kind, started_at=exc.started_at,
                                 ended_at=ts, peak_c=exc.peak_c, note=_NOTES[kind], seq=self._seq))
            if self.has(FAILURE):
                ev = self._close(FAILURE, ts)
                if ev:
                    out.append(ev)
            self._excursion_saw_door = False

            # 4. small bump below the limit = defrost ----------------------
            rise = air_c - setpoint
            if 0.8 <= rise < config.DEFROST_MAX_RISE_C and not self.has(DEFROST) and not door_open:
                # Opened quietly: a defrost cycle is only worth logging once it
                # has lasted long enough to be a cycle and not a passing wobble.
                self._start(DEFROST, ts, air_c)
            elif self.has(DEFROST):
                ev = self._open[DEFROST]
                ev.peak_c = max(ev.peak_c or air_c, air_c)
                if rise < 0.6:
                    ev = self._close(DEFROST, ts)
                    if ev and ev.ended_at - ev.started_at >= config.DEFROST_MIN_S:
                        out.append(ev)

        self.last_ts, self.last_air = ts, air_c
        return out
