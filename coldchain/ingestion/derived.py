"""Derived values this platform owns (spec, section 10).

Distance, speed, temperature deviation, time above threshold, door duration
and ETA. All of it is arithmetic over the telemetry stream.

Where the line sits: thermal exposure is accumulated here because it is a sum
over the readings we hold — but what that exposure *means* for the food (a
spoilage probability, a remaining shelf life, a risk level) is Person 4's
model, and nothing in this file tries to answer it.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Optional

from .. import config
from ..fleet import haversine_km
from ..opendata.offline import condensation_risk, dew_point_c
from ..schemas import Derived, Telemetry


@dataclass
class TruckAccumulator:
    """Running state for one truck, updated on every accepted reading."""

    truck_id: str
    readings: Deque[Telemetry] = field(default_factory=lambda: deque(maxlen=config.WINDOW_SIZE))
    trip_distance_km: float = 0.0
    time_above_threshold_s: float = 0.0
    thermal_exposure_c_min: float = 0.0
    door_open_duration_s: float = 0.0
    refrigeration_off_duration_s: float = 0.0
    _last: Optional[Telemetry] = None

    def reset(self) -> None:
        self.readings.clear()
        self.trip_distance_km = 0.0
        self.time_above_threshold_s = 0.0
        self.thermal_exposure_c_min = 0.0
        self.door_open_duration_s = 0.0
        self.refrigeration_off_duration_s = 0.0
        self._last = None

    def update(self, t: Telemetry, *, safe_max_c: float | None,
               destination: tuple[float, float] | None) -> Derived:
        """Fold one reading in and return the derived block for it."""
        prev = self._last
        dt_s = 0.0
        step_km = 0.0

        if prev is not None:
            dt_s = max(0.0, (t.timestamp - prev.timestamp).total_seconds())
            step_km = haversine_km(prev.latitude, prev.longitude,
                                   t.latitude, t.longitude)
            self.trip_distance_km += step_km

            # Durations are credited to the interval that just closed, using
            # the state the truck was in during it.
            if prev.door_open:
                self.door_open_duration_s += dt_s
            if not prev.refrigeration_on:
                self.refrigeration_off_duration_s += dt_s
            if safe_max_c is not None and prev.temperature_c > safe_max_c:
                self.time_above_threshold_s += dt_s
                # E_T = sum max(0, T_i - T_safe) * dt, in degree-minutes.
                self.thermal_exposure_c_min += (prev.temperature_c - safe_max_c) * (dt_s / 60.0)

        deviation = 0.0
        if safe_max_c is not None and t.temperature_c > safe_max_c:
            deviation = t.temperature_c - safe_max_c

        # Condensation is the failure a thermometer alone misses: warm humid
        # air meeting a cold pallet at an open door wets the product, and wet
        # cartons grow mould long before temperature would have spoiled them.
        #
        # The risk is judged against the product's own safe maximum, on the
        # stated assumption that a pallet whose chain has held sits at or
        # below it. This service has no cargo-temperature model of its own
        # and does not pretend to: with no product limit there is no risk to
        # report, only the dew point.
        dew_c: float | None = None
        wets: bool | None = None
        if t.humidity_pct is not None:
            dew_c = round(dew_point_c(t.temperature_c, t.humidity_pct), 2)
            if safe_max_c is not None:
                wets = bool(t.door_open and condensation_risk(
                    safe_max_c, t.temperature_c, t.humidity_pct))

        dist_to_dest: float | None = None
        eta_min: float | None = None
        if destination is not None:
            dist_to_dest = haversine_km(t.latitude, t.longitude,
                                        destination[0], destination[1])
            # A stationary truck still has an ETA: fall back to a cruising
            # speed rather than reporting infinity.
            speed = t.speed_kmh if t.speed_kmh > 1.0 else config.ETA_FALLBACK_KMH
            eta_min = (dist_to_dest / speed) * 60.0

        self.readings.append(t)
        self._last = t

        return Derived(
            distance_km=round(step_km, 4),
            trip_distance_km=round(self.trip_distance_km, 3),
            temperature_deviation_c=round(deviation, 2),
            time_above_threshold_s=round(self.time_above_threshold_s, 1),
            thermal_exposure_c_min=round(self.thermal_exposure_c_min, 2),
            door_open_duration_s=round(self.door_open_duration_s, 1),
            refrigeration_off_duration_s=round(self.refrigeration_off_duration_s, 1),
            distance_to_destination_km=None if dist_to_dest is None else round(dist_to_dest, 3),
            eta_minutes=None if eta_min is None else round(eta_min, 1),
            dew_point_c=dew_c,
            condensation_risk=wets,
        )

    def recent(self, limit: int = 60) -> list[Telemetry]:
        return list(self.readings)[-limit:]

    def current_door_run_s(self, now: datetime) -> float:
        """How long the door has been open in the run that is still open."""
        if self._last is None or not self._last.door_open:
            return 0.0
        run = 0.0
        for r in reversed(self.readings):
            if not r.door_open:
                break
            run = (now - r.timestamp).total_seconds()
        return max(0.0, run)

    def current_refrigeration_off_run_s(self, now: datetime) -> float:
        if self._last is None or self._last.refrigeration_on:
            return 0.0
        run = 0.0
        for r in reversed(self.readings):
            if r.refrigeration_on:
                break
            run = (now - r.timestamp).total_seconds()
        return max(0.0, run)

    def current_excursion_run_s(self, safe_max_c: float | None) -> float:
        """Unbroken seconds the temperature has been above the safe maximum."""
        if safe_max_c is None or self._last is None:
            return 0.0
        if self._last.temperature_c <= safe_max_c:
            return 0.0
        newest = self._last.timestamp
        oldest = newest
        for r in reversed(self.readings):
            if r.temperature_c <= safe_max_c:
                break
            oldest = r.timestamp
        return max(0.0, (newest - oldest).total_seconds())

    def peak_temperature_c(self) -> float | None:
        return max((r.temperature_c for r in self.readings), default=None)
