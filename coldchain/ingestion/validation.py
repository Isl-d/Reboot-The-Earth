"""Validate and normalize a raw reading (spec: "Data quality").

Two rules drive this module:

* Reject anything physically implausible — a temperature of -127 from a dead
  sensor, a humidity of 140, a latitude of 900.
* Never silently drop. Every rejection carries a machine-readable reason and
  a human sentence, and the caller writes both to `rejected_readings`.

Normalization is the other half: a device may send a short field name, omit
its truck id, or leave the timestamp off. Anything we can fill in without
guessing at a measurement, we fill in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .. import clock, config
from ..schemas import (DEVICE_EVENT_TYPES, DeviceEvent, DeviceEventIn,
                       Telemetry, TelemetryIn)


class ValidationError(Exception):
    """Raised with a short reason code and a readable explanation."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass
class Rejection:
    reason: str
    detail: str
    truck_id: str


def _truck_from_device(device_id: str | None) -> Optional[str]:
    """`TRUCK-T102` -> `T102`. Anything else stays unknown."""
    if device_id and device_id.upper().startswith("TRUCK-"):
        return device_id.split("-", 1)[1]
    return None


def _range(name: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise ValidationError(
            f"{name}_out_of_range",
            f"{name} was {value}, outside the plausible range {low} to {high}")


def normalize(payload: dict[str, Any], *, topic: str | None = None,
              now: datetime | None = None) -> Telemetry:
    """Turn a raw payload into a complete, in-range reading, or raise.

    `topic` is used only to recover a truck id the payload forgot; a topic
    that disagrees with the payload is a conflict, not something to guess at.
    """
    now = now or clock.now()

    try:
        raw = TelemetryIn.from_payload(payload)
    except Exception as exc:                        # noqa: BLE001
        raise ValidationError("unparseable", f"payload did not parse: {exc}") from exc

    topic_truck = None
    if topic:
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == "coldchain" and parts[1] == "trucks":
            topic_truck = parts[2]

    truck_id = raw.truck_id or _truck_from_device(raw.device_id) or topic_truck
    if not truck_id:
        raise ValidationError("missing_truck_id",
                              "no truckId, no deviceId to derive it from, and no topic")
    # The check covers the derived id too: a device whose id disagrees with
    # the topic it published on is a wiring fault, not something to guess at.
    if topic_truck and topic_truck != truck_id:
        raise ValidationError(
            "truck_id_conflict",
            f"topic says {topic_truck} but the payload resolves to {truck_id}")

    device_id = raw.device_id or f"TRUCK-{truck_id}"

    ts = raw.timestamp or now
    ts = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    skew = (ts - now).total_seconds()
    if skew > config.CLOCK_SKEW_FUTURE_S:
        raise ValidationError("timestamp_in_future",
                              f"timestamp is {skew:.0f}s ahead of the server clock")
    if -skew > config.CLOCK_SKEW_PAST_S:
        raise ValidationError("timestamp_too_old",
                              f"timestamp is {-skew:.0f}s behind the server clock")

    if raw.temperature_c is None:
        raise ValidationError("missing_temperature", "no temperature in the payload")
    if raw.latitude is None or raw.longitude is None:
        raise ValidationError("missing_position", "no latitude/longitude in the payload")

    _range("temperature", raw.temperature_c, config.TEMP_MIN_C, config.TEMP_MAX_C)
    _range("latitude", raw.latitude, -90.0, 90.0)
    _range("longitude", raw.longitude, -180.0, 180.0)

    humidity = raw.humidity_pct
    if humidity is not None:
        _range("humidity", humidity, config.HUMIDITY_MIN_PCT,
               config.HUMIDITY_MAX_PCT)

    speed = 0.0 if raw.speed_kmh is None else raw.speed_kmh
    if speed < 0:
        raise ValidationError("negative_speed", f"speed was {speed}")
    _range("speed", speed, 0.0, config.SPEED_MAX_KMH)

    g = 0.0 if raw.g_force is None else raw.g_force
    if g < 0:
        raise ValidationError("negative_gforce", f"gForce was {g}")
    _range("gforce", g, 0.0, config.GFORCE_MAX)

    return Telemetry(
        device_id=device_id,
        truck_id=truck_id,
        timestamp=ts,
        temperature_c=float(raw.temperature_c),
        humidity_pct=None if humidity is None else float(humidity),
        latitude=float(raw.latitude),
        longitude=float(raw.longitude),
        speed_kmh=float(speed),
        g_force=float(g),
        door_open=bool(raw.door_open) if raw.door_open is not None else False,
        refrigeration_on=bool(raw.refrigeration_on) if raw.refrigeration_on is not None else True,
    )


def _truck_from_topic(topic: str | None) -> Optional[str]:
    if not topic:
        return None
    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "coldchain" and parts[1] == "trucks":
        return parts[2]
    return None


def normalize_event(payload: dict[str, Any], *, topic: str | None = None,
                    now: datetime | None = None) -> DeviceEvent:
    """Validate a device event, or raise.

    Identity is recovered the same way as telemetry — payload, then deviceId,
    then topic — so a device that reports events but not its own id still
    works. An unknown event type is rejected rather than stored: a type the
    dashboard cannot render is not useful, and inventing a catch-all would
    hide a device sending the wrong thing.
    """
    now = now or clock.now()

    try:
        raw = DeviceEventIn.model_validate(payload)
    except Exception as exc:                        # noqa: BLE001
        raise ValidationError("unparseable", f"event did not parse: {exc}") from exc

    topic_truck = _truck_from_topic(topic)
    truck_id = raw.truck_id or _truck_from_device(raw.device_id) or topic_truck
    if not truck_id:
        raise ValidationError("missing_truck_id",
                              "no truckId, no deviceId to derive it from, and no topic")
    if topic_truck and topic_truck != truck_id:
        raise ValidationError(
            "truck_id_conflict",
            f"topic says {topic_truck} but the payload resolves to {truck_id}")

    if not raw.type:
        raise ValidationError("missing_event_type", "no type in the payload")
    kind = str(raw.type).upper()
    if kind not in DEVICE_EVENT_TYPES:
        raise ValidationError(
            "unknown_event_type",
            f"{kind!r} is not one of {', '.join(DEVICE_EVENT_TYPES)}")

    ts = raw.timestamp or now
    ts = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    skew = (ts - now).total_seconds()
    if skew > config.CLOCK_SKEW_FUTURE_S:
        raise ValidationError("timestamp_in_future",
                              f"timestamp is {skew:.0f}s ahead of the server clock")
    if -skew > config.CLOCK_SKEW_PAST_S:
        raise ValidationError("timestamp_too_old",
                              f"timestamp is {-skew:.0f}s behind the server clock")

    return DeviceEvent(device_id=raw.device_id or f"TRUCK-{truck_id}",
                       truck_id=truck_id, timestamp=ts, type=kind,
                       detail=raw.detail or "", value=raw.value)
