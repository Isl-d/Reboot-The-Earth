"""Every tunable for the Person 3 data platform, in one place.

Nothing here is a secret. Every value can be overridden with a COLDCHAIN_*
environment variable so the demo laptop never needs a code change.
"""
from __future__ import annotations

import os
import uuid


def _env(name: str, default: str) -> str:
    return os.environ.get(f"COLDCHAIN_{name}", default)


def _num(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


# --------------------------------------------------------------- transports
MQTT_HOST = _env("MQTT_HOST", "localhost")
MQTT_PORT = int(_num("MQTT_PORT", 1883))
# An MQTT broker evicts an existing client when a new one connects with the
# same id, so two instances of this service would thrash. Default to a unique
# id per process; set COLDCHAIN_MQTT_CLIENT_ID when you want a fixed one.
MQTT_CLIENT_ID = _env("MQTT_CLIENT_ID", f"coldchain-ingest-{os.getpid()}-{uuid.uuid4().hex[:6]}")
TELEMETRY_TOPIC = "coldchain/trucks/{truck_id}/telemetry"
EVENTS_TOPIC = "coldchain/trucks/{truck_id}/events"
TELEMETRY_WILDCARD = "coldchain/trucks/+/telemetry"
EVENTS_WILDCARD = "coldchain/trucks/+/events"

# Empty means "run in memory only". The platform must never fall over on
# stage because Postgres or Redis is missing.
DATABASE_URL = _env("DATABASE_URL", "postgresql+psycopg://coldchain:coldchain@localhost:5432/coldchain")
REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")

API_HOST = _env("API_HOST", "0.0.0.0")
API_PORT = int(_num("API_PORT", 8100))

# ------------------------------------------------------------ simulator
TICK_SECONDS = _num("TICK_SECONDS", 2.0)          # spec: every 2-5 s
SIM_SEED = int(_num("SIM_SEED", 7))
DEFAULT_SPEED_MULTIPLIER = _num("SPEED_MULTIPLIER", 1.0)

# ------------------------------------------------------------ validation
# Physically plausible bounds. A reading outside these is rejected and logged,
# never silently dropped (spec: "Data quality").
TEMP_MIN_C = _num("TEMP_MIN_C", -40.0)
TEMP_MAX_C = _num("TEMP_MAX_C", 80.0)
HUMIDITY_MIN_PCT = _num("HUMIDITY_MIN_PCT", 0.0)
HUMIDITY_MAX_PCT = _num("HUMIDITY_MAX_PCT", 100.0)
SPEED_MAX_KMH = _num("SPEED_MAX_KMH", 200.0)
GFORCE_MAX = _num("GFORCE_MAX", 16.0)
# A timestamp further than this from now is treated as a clock fault.
CLOCK_SKEW_PAST_S = _num("CLOCK_SKEW_PAST_S", 86_400.0)
CLOCK_SKEW_FUTURE_S = _num("CLOCK_SKEW_FUTURE_S", 300.0)

# ------------------------------------------------------------ derived values
# Rolling window kept per truck for derived values and the Person 4 bundle.
WINDOW_SIZE = int(_num("WINDOW_SIZE", 240))
# A door open longer than this is an incident, not a delivery stop.
DOOR_OPEN_INCIDENT_S = _num("DOOR_OPEN_INCIDENT_S", 120.0)
# Sustained time above the batch's safe maximum before an incident opens.
EXCURSION_INCIDENT_S = _num("EXCURSION_INCIDENT_S", 60.0)
# Refrigeration reported off for this long is an incident on its own.
REFRIGERATION_INCIDENT_S = _num("REFRIGERATION_INCIDENT_S", 60.0)
# A shock above this opens a handling incident.
GFORCE_INCIDENT = _num("GFORCE_INCIDENT", 2.0)
# Assumed cruising speed when a truck is stationary, for ETA.
ETA_FALLBACK_KMH = _num("ETA_FALLBACK_KMH", 40.0)

REDIS_TTL_S = int(_num("REDIS_TTL_S", 3600))
