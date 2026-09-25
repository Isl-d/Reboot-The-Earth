"""The scenario engine (spec, section 2).

Each scenario is a small physical model of one thing going wrong, driving the
temperature, the door, the cooling unit and the road speed. A truck holds its
own state and steps forward; nothing here reaches for a clock, so a test can
step a hundred ticks in a millisecond and get the same numbers every time.

Temperature follows a first-order lag towards a target that depends on the
scenario, which is what a real box does — a fridge does not jump, it drifts.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from .. import clock, fleet

NORMAL = "NORMAL"
TEMPERATURE_EXCURSION = "TEMPERATURE_EXCURSION"
DOOR_LEFT_OPEN = "DOOR_LEFT_OPEN"
REFRIGERATION_FAILURE = "REFRIGERATION_FAILURE"
TRAFFIC_DELAY = "TRAFFIC_DELAY"
COMBINED_FAILURE = "COMBINED_FAILURE"

ALL = (NORMAL, TEMPERATURE_EXCURSION, DOOR_LEFT_OPEN, REFRIGERATION_FAILURE,
       TRAFFIC_DELAY, COMBINED_FAILURE)

OUTSIDE_C = 41.0          # a Gulf afternoon
CRUISE_KMH = 60.0


@dataclass
class SimTruck:
    """One simulated refrigerated truck walking its route."""

    truck_id: str
    route_id: str
    batch: dict
    rng: random.Random
    scenario: str = NORMAL
    temperature_c: float = 3.0
    humidity_pct: float = 72.0
    speed_kmh: float = CRUISE_KMH
    g_force: float = 0.15
    door_open: bool = False
    refrigeration_on: bool = True
    progress_km: float = 0.0
    elapsed_s: float = 0.0
    _scenario_started_s: float = 0.0
    _pending_events: list = field(default_factory=list)
    _route: dict = field(init=False)
    _length_km: float = field(init=False)

    def __post_init__(self) -> None:
        self._route = fleet.route_by_id(self.route_id) or fleet.ROUTES[0]
        self._length_km = fleet.route_length_km(self._route)
        setpoint = (self.batch["safe_min_temp_c"] + self.batch["safe_max_temp_c"]) / 2
        self.temperature_c = setpoint

    # ------------------------------------------------------------ control
    def set_scenario(self, scenario: str) -> None:
        if scenario not in ALL:
            raise ValueError(f"unknown scenario {scenario!r}")
        self.scenario = scenario
        self._scenario_started_s = self.elapsed_s
        # Faults that are a state, not a drift, take effect at once.
        was_door, was_fridge = self.door_open, self.refrigeration_on
        self.door_open = scenario in (DOOR_LEFT_OPEN, COMBINED_FAILURE)
        self.refrigeration_on = scenario not in (REFRIGERATION_FAILURE, COMBINED_FAILURE)
        if self.door_open != was_door:
            self._event("DOOR_OPENED" if self.door_open else "DOOR_CLOSED")
        if self.refrigeration_on != was_fridge:
            self._event("REFRIGERATION_ON" if self.refrigeration_on
                        else "REFRIGERATION_OFF", "reported by the unit")

    # ------------------------------------------------------------- physics
    def _target_and_rate(self) -> tuple[float, float]:
        """Where the air in the box is heading, and how fast it gets there."""
        setpoint = (self.batch["safe_min_temp_c"] + self.batch["safe_max_temp_c"]) / 2
        safe_max = self.batch["safe_max_temp_c"]

        if self.scenario == NORMAL:
            return setpoint, 0.25
        if self.scenario == TEMPERATURE_EXCURSION:
            # Creeps past the limit and settles a few degrees above it.
            return safe_max + 3.5, 0.06
        if self.scenario == DOOR_LEFT_OPEN:
            # Warm air leaks in; the unit fights it, so it stalls below outside.
            return min(OUTSIDE_C, safe_max + 9.0), 0.08
        if self.scenario == REFRIGERATION_FAILURE:
            # Nothing is fighting the heat any more.
            return OUTSIDE_C, 0.16
        if self.scenario == TRAFFIC_DELAY:
            return setpoint, 0.25
        if self.scenario == COMBINED_FAILURE:
            return OUTSIDE_C, 0.22
        return setpoint, 0.25

    def _target_speed(self) -> float:
        if self.scenario in (TRAFFIC_DELAY, COMBINED_FAILURE):
            return 8.0
        return CRUISE_KMH

    def drain_events(self) -> list[dict]:
        """Device events since the last call: what changed, the moment it did.

        A real unit reports a door or a compressor the instant it trips,
        rather than waiting for the next telemetry tick.
        """
        out, self._pending_events = self._pending_events, []
        return out

    def _event(self, kind: str, detail: str = "", value: float | None = None) -> None:
        self._pending_events.append({
            "deviceId": fleet.device_id(self.truck_id),
            "truckId": self.truck_id,
            "timestamp": self._stamp(),
            "type": kind,
            "detail": detail,
            "value": value,
        })

    def step(self, dt_s: float) -> dict:
        """Advance by dt_s seconds and return one telemetry payload."""
        self.elapsed_s += dt_s
        was_door, was_fridge = self.door_open, self.refrigeration_on

        target_c, rate = self._target_and_rate()
        self.temperature_c += (target_c - self.temperature_c) * min(1.0, rate)
        self.temperature_c += self.rng.uniform(-0.08, 0.08)      # sensor noise

        # Humidity rises with the door open and falls as the unit dries the air.
        h_target = 88.0 if self.door_open else 70.0
        self.humidity_pct += (h_target - self.humidity_pct) * 0.15
        self.humidity_pct = max(0.0, min(100.0, self.humidity_pct + self.rng.uniform(-0.5, 0.5)))

        target_speed = self._target_speed()
        self.speed_kmh += (target_speed - self.speed_kmh) * 0.3
        self.speed_kmh = max(0.0, self.speed_kmh + self.rng.uniform(-1.2, 1.2))

        # A pothole every so often; rough handling shows up as a shock.
        self.g_force = round(abs(self.rng.gauss(0.18, 0.08)), 2)
        if self.rng.random() < 0.01:
            self.g_force = round(self.rng.uniform(2.1, 3.4), 2)
            self._event("SHOCK", "rough handling detected", self.g_force)

        if self.door_open != was_door:
            self._event("DOOR_OPENED" if self.door_open else "DOOR_CLOSED")
        if self.refrigeration_on != was_fridge:
            self._event("REFRIGERATION_ON" if self.refrigeration_on
                        else "REFRIGERATION_OFF", "reported by the unit")

        self.progress_km = min(self._length_km,
                               self.progress_km + self.speed_kmh * (dt_s / 3600.0))
        lat, lon = self._position()

        return {
            "deviceId": fleet.device_id(self.truck_id),
            "truckId": self.truck_id,
            "timestamp": self._stamp(),
            "temperatureC": round(self.temperature_c, 1),
            "humidityPct": round(self.humidity_pct),
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "speedKmh": round(self.speed_kmh, 1),
            "gForce": self.g_force,
            "doorOpen": self.door_open,
            "refrigerationOn": self.refrigeration_on,
        }

    def _stamp(self) -> str:
        # The platform clock, so an accelerated run stays internally
        # consistent (see coldchain/clock.py).
        return clock.now().isoformat().replace("+00:00", "Z")

    def _position(self) -> tuple[float, float]:
        """Interpolate along the route polyline by distance travelled."""
        g = self._route["geometry"]
        if len(g) < 2:
            return g[0][1], g[0][0]
        remaining = self.progress_km
        for i in range(len(g) - 1):
            lon1, lat1 = g[i]
            lon2, lat2 = g[i + 1]
            seg = fleet.haversine_km(lat1, lon1, lat2, lon2)
            if remaining <= seg or i == len(g) - 2:
                f = 0.0 if seg == 0 else min(1.0, remaining / seg)
                return lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f
            remaining -= seg
        return g[-1][1], g[-1][0]


def build_fleet(seed: int = 7) -> dict[str, SimTruck]:
    """One SimTruck per truck in the demo world, deterministic for `seed`."""
    rng = random.Random(seed)
    out: dict[str, SimTruck] = {}
    for t in fleet.TRUCKS:
        batch = fleet.batch_for_truck(t["id"])
        if batch is None:
            continue
        out[t["id"]] = SimTruck(truck_id=t["id"], route_id=t["route_id"],
                                batch=batch, rng=random.Random(rng.random() * 1e9))
    return out
