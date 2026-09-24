"""Single place for every tunable number in ColdGuard.

Nothing here is a secret: Wi-Fi credentials live in the firmware only.
Every value can be overridden with a COLDGUARD_* environment variable
(see .env.example), so the demo laptop never needs a code change.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _s(name: str, default: str) -> str:
    return os.getenv(name, default)


# --- infrastructure -------------------------------------------------------
MQTT_HOST = _s("COLDGUARD_MQTT_HOST", "localhost")
MQTT_PORT = _i("COLDGUARD_MQTT_PORT", 1883)
TELEMETRY_TOPIC = "coldguard/+/telemetry"
CONTROL_TOPIC = "coldguard/control/{truck_id}"

DB_URL = _s("COLDGUARD_DB_URL", "")           # empty -> in-memory only
OLLAMA_URL = _s("COLDGUARD_OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = _s("COLDGUARD_OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT_S = _f("COLDGUARD_OLLAMA_TIMEOUT_S", 5.0)

# --- physics --------------------------------------------------------------
# Two tonnes of lettuce do not follow a 2-second air reading. The air sensor
# spikes at once (that is what the detector watches); the core temperature of
# the pallet follows with a first-order lag. The shelf-life clock uses the
# product temperature, which is what the food actually experiences.
PRODUCT_LAG_H = _f("COLDGUARD_PRODUCT_LAG_H", 2.0)     # simulated hours to 63 %
# Risk shown on the dashboard assumes a warm spell is fixed within this many
# hours - unless the detector has confirmed a cooling failure, in which case
# the projection is the honest worst case: it stays broken all the way.
WARM_PROJECTION_H = _f("COLDGUARD_WARM_PROJECTION_H", 1.0)

# --- demo clock -----------------------------------------------------------
# 1 real second on stage = DEMO_SPEED simulated seconds. Always shown on screen.
# This is the shelf-life clock: it is what makes spoilage visible in minutes.
DEMO_SPEED = _f("COLDGUARD_DEMO_SPEED", 120.0)
# Positions are animated more slowly, so a truck crosses its route over the
# four minutes of the demo instead of arriving in twenty seconds. Pass the same
# number to the simulator with --demo-speed. Both rates are shown on screen.
MAP_SPEED = _f("COLDGUARD_MAP_SPEED", 10.0)

# --- detector thresholds (demo values; real-world values in brackets) -----
DOOR_WINDOW_S = _f("COLDGUARD_DOOR_WINDOW_S", 20.0)        # [10 min] transient rise
FAILURE_HOLD_S = _f("COLDGUARD_FAILURE_HOLD_S", 35.0)      # [10 min] above alert limit
DEFROST_MAX_RISE_C = _f("COLDGUARD_DEFROST_MAX_RISE_C", 2.0)
DEFROST_MIN_S = _f("COLDGUARD_DEFROST_MIN_S", 6.0)      # shorter bumps are just noise
SENSOR_GAP_S = _f("COLDGUARD_SENSOR_GAP_S", 10.0)          # no reading for this long
SENSOR_JUMP_C = _f("COLDGUARD_SENSOR_JUMP_C", 15.0)        # jump between readings
SENSOR_SENTINEL_C = -127.0
# Temperature must not be clearly falling for a cooling failure to be declared.
FAILURE_MAX_FALL_C_PER_S = _f("COLDGUARD_FAILURE_MAX_FALL_C_PER_S", 0.05)
HISTORY_POINTS = _i("COLDGUARD_HISTORY_POINTS", 900)       # per truck ring buffer

# --- planner economics ----------------------------------------------------
COST_PER_KM_QAR = _f("COLDGUARD_COST_PER_KM_QAR", 3.5)     # diesel + driver, demo figure
MARKDOWN_FRACTION = _f("COLDGUARD_MARKDOWN_FRACTION", 0.5)  # sell now at -50 %
DONATION_VALUE_FRACTION = _f("COLDGUARD_DONATION_VALUE_FRACTION", 0.3)
# Never disturb a shipment that is fine: another option must beat "continue as
# planned" by at least this much before it is recommended.
REROUTE_MIN_GAIN_QAR = _f("COLDGUARD_REROUTE_MIN_GAIN_QAR", 500.0)
ROAD_FACTOR = _f("COLDGUARD_ROAD_FACTOR", 1.3)             # straight line -> road km
TRUCK_SPEED_KMH = _f("COLDGUARD_TRUCK_SPEED_KMH", 60.0)
# Hours between arriving at a node and the food reaching a shelf. Going through
# the distribution warehouse costs most of a day; delivering straight to a store
# costs a couple of hours. This is why option C buys back shelf life.
HANDOVER_WAREHOUSE_H = _f("COLDGUARD_HANDOVER_WAREHOUSE_H", 20.0)
HANDOVER_STORE_H = _f("COLDGUARD_HANDOVER_STORE_H", 1.0)

# --- impact accounting (for the comparison screen) ------------------------
# Emissions avoided when food is not thrown away, kg CO2e per kg of food.
# FAO food-loss footprint, order-of-magnitude figure used for the demo only.
CO2E_PER_KG_FOOD = _f("COLDGUARD_CO2E_PER_KG_FOOD", 2.5)

# Every shipment leaves the port with 80 % of its shelf life: 8 days for
# lettuce, matching the demo scenario in CLAUDE.md section 8.
START_LIFE_FRACTION = _f("COLDGUARD_START_LIFE_FRACTION", 0.8)

REAL_TRUCK = "TRK-07"
