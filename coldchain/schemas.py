"""Wire contracts for the data platform (Person 3).

The JSON on the wire is camelCase, exactly as the brief specifies, so Person 1
and Person 2 can type against it directly. Inside Python the fields keep their
snake_case names.

Ingest is deliberately tolerant about two spellings of the same reading: the
full form (`temperatureC`, `humidityPct`) and the short form (`temperature`,
`humidity`, `lat`, `lon`) that the MQTT message example uses. Anything a real
device might send and we can understand without guessing, we accept.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class Wire(BaseModel):
    """Base for everything that crosses the network: camelCase in and out."""

    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True,
                              extra="ignore")


# ------------------------------------------------------------------ telemetry
class TelemetryIn(Wire):
    """A raw reading as it arrives from a device or the simulator."""

    device_id: Optional[str] = None
    truck_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    temperature_c: Optional[float] = Field(default=None, validation_alias="temperatureC")
    humidity_pct: Optional[float] = Field(default=None, validation_alias="humidityPct")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_kmh: Optional[float] = Field(default=None, validation_alias="speedKmh")
    g_force: Optional[float] = Field(default=None, validation_alias="gForce")
    door_open: Optional[bool] = None
    refrigeration_on: Optional[bool] = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TelemetryIn":
        """Accept the short spelling of the MQTT example as well as the full one."""
        p = dict(payload)
        for short, full in (("temperature", "temperatureC"), ("humidity", "humidityPct"),
                            ("lat", "latitude"), ("lon", "longitude"),
                            ("speed", "speedKmh"), ("refrigeration", "refrigerationOn")):
            if short in p and full not in p:
                p[full] = p.pop(short)
        return cls.model_validate(p)


class Telemetry(Wire):
    """A validated, normalized reading. Every field is present and in range."""

    device_id: str
    truck_id: str
    timestamp: datetime
    temperature_c: float
    # Absent is null, never 0.0: a fridge does not read zero per cent, and a
    # fabricated value would plot as a measurement on the humidity chart.
    humidity_pct: Optional[float] = None
    latitude: float
    longitude: float
    speed_kmh: float
    g_force: float
    door_open: bool
    refrigeration_on: bool

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)


class Derived(Wire):
    """Values this platform computes from the stream itself.

    These are arithmetic on the telemetry — distance, durations, deviation —
    and deliberately stop short of the deterioration model, which Person 4
    owns. No spoilage probability or shelf life is computed here.
    """

    distance_km: float = 0.0
    trip_distance_km: float = 0.0
    temperature_deviation_c: float = 0.0
    time_above_threshold_s: float = 0.0
    thermal_exposure_c_min: float = 0.0
    door_open_duration_s: float = 0.0
    refrigeration_off_duration_s: float = 0.0
    distance_to_destination_km: Optional[float] = None
    eta_minutes: Optional[float] = None
    # Open psychrometrics (Magnus/Tetens). Null when the device reports no
    # humidity, because a dew point without one would be invented.
    dew_point_c: Optional[float] = None
    condensation_risk: Optional[bool] = None


class TruckState(Wire):
    """What the map and the fleet table read: the latest of everything."""

    truck_id: str
    device_id: Optional[str] = None
    plate: Optional[str] = None
    status: str = "IDLE"
    scenario: str = "NORMAL"
    batch_id: Optional[str] = None
    product: Optional[str] = None
    quantity_kg: Optional[float] = None
    destination_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    speed_kmh: Optional[float] = None
    g_force: Optional[float] = None
    door_open: Optional[bool] = None
    refrigeration_on: Optional[bool] = None
    safe_min_temp_c: Optional[float] = None
    safe_max_temp_c: Optional[float] = None
    timestamp: Optional[datetime] = None
    derived: Derived = Field(default_factory=Derived)
    # Owned by Person 4 and merely carried here. Null until a prediction is
    # posted to /api/internal/predictions.
    risk_score: Optional[float] = None
    risk_level: str = "UNKNOWN"


# ------------------------------------------------------------- device events
#
# The brief names `coldchain/trucks/{truckId}/events` but does not define its
# payload, so this contract is ours. It exists because a device can report a
# door opening the instant it happens, while telemetry only arrives every
# 2-5 s — and a door state is what explains a temperature excursion.
#
# Events say what the device observed. They never carry a risk or a
# prediction; that boundary is the same as everywhere else in this service.

DeviceEventType = Literal["DOOR_OPENED", "DOOR_CLOSED", "REFRIGERATION_ON",
                          "REFRIGERATION_OFF", "SHOCK", "POWER_LOST",
                          "POWER_RESTORED", "SENSOR_FAULT"]

DEVICE_EVENT_TYPES = ("DOOR_OPENED", "DOOR_CLOSED", "REFRIGERATION_ON",
                      "REFRIGERATION_OFF", "SHOCK", "POWER_LOST",
                      "POWER_RESTORED", "SENSOR_FAULT")


class DeviceEventIn(Wire):
    """A raw event as it arrives on the events topic."""

    device_id: Optional[str] = None
    truck_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    type: Optional[str] = None
    detail: Optional[str] = None
    value: Optional[float] = None


class DeviceEvent(Wire):
    """A validated device event."""

    device_id: str
    truck_id: str
    timestamp: datetime
    type: DeviceEventType
    detail: str = ""
    value: Optional[float] = None

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ reference
class Warehouse(Wire):
    id: str
    name: str
    latitude: float
    longitude: float
    capacity_kg: float
    available_capacity_kg: float
    min_temp_c: float
    max_temp_c: float


class Store(Wire):
    id: str
    name: str
    latitude: float
    longitude: float


class Batch(Wire):
    id: str
    product: str
    quantity_kg: float
    production_date: str
    expiry_date: str
    safe_min_temp_c: float
    safe_max_temp_c: float
    initial_shelf_life_hours: float
    truck_id: Optional[str] = None


class Incident(Wire):
    id: str
    truck_id: str
    type: str
    severity: str
    status: str = "OPEN"
    opened_at: datetime
    closed_at: Optional[datetime] = None
    detail: str = ""
    peak_temperature_c: Optional[float] = None

    @field_validator("opened_at", "closed_at")
    @classmethod
    def _utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        # SQLite hands back naive datetimes. Incidents are sorted by time, and
        # mixing naive with aware raises — which would take out the incident
        # panel after a restart. Normalize on the way in.
        if v is None:
            return None
        return v.astimezone(timezone.utc) if v.tzinfo else v.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ control
Scenario = Literal["NORMAL", "TEMPERATURE_EXCURSION", "DOOR_LEFT_OPEN",
                   "REFRIGERATION_FAILURE", "TRAFFIC_DELAY", "COMBINED_FAILURE"]


class ScenarioRequest(Wire):
    truck_id: str
    scenario: Scenario
    # None means "leave the current speed alone". A default of 1.0 here would
    # silently undo a x10 run every time a scenario is set.
    speed_multiplier: Optional[float] = None


class SimulationRequest(Wire):
    speed_multiplier: float = 1.0
    scenario: Optional[Scenario] = None


# ------------------------------------------------ handed to / from Person 4
class PredictionIn(Wire):
    """What Person 4 posts back. This platform stores and forwards it."""

    truck_id: str
    spoilage_probability: Optional[float] = None
    remaining_shelf_life: Optional[float] = None
    thermal_exposure: Optional[float] = None
    confidence: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None


class RecommendationIn(Wire):
    truck_id: str
    action: str
    destination: Optional[str] = None
    eta: Optional[float] = None
    expected_loss: float = 0.0
    food_saved: float = 0.0
    reasoning: str = ""
