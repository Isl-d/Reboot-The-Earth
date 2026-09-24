"""Record reference traces from simulator/sim.py so the tests never need MQTT.

    python tests/traces/make_traces.py

Writes one JSON file per scenario: a list of {t, air_c, door_open}. The seed is
fixed, so the recorded trace is the same trace the judges will see on stage.
"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "simulator"))

from sim import Truck, load_products, load_routes          # noqa: E402

HERE = Path(__file__).resolve().parent
INTERVAL = 2.0
OUTSIDE = 41.0


def record(name: str, seconds: float, script) -> None:
    rng = random.Random(7)
    routes, products = load_routes(), load_products()
    truck = Truck("TRK-03", "R3", "lettuce", 1500, 0.3, products, rng)
    route = routes["R3"]
    rows, t = [], 0.0
    while t < seconds:
        script(truck, t)
        msg = truck.step(INTERVAL, 120.0, route, OUTSIDE)
        rows.append({"t": round(t, 1), "air_c": msg["air_c"], "door_open": msg["door_open"]})
        t += INTERVAL
    (HERE / f"{name}.json").write_text(json.dumps(rows, indent=1))
    peak = max(r["air_c"] for r in rows)
    print(f"{name:14s} {len(rows):3d} readings, peak {peak:5.1f} C -> {name}.json")


def main() -> None:
    record("steady", 60, lambda tr, t: None)
    record("door", 120, lambda tr, t: tr.control({"fault": "door", "on": True}) if t == 20.0 else None)
    record("compressor", 240,
           lambda tr, t: tr.control({"fault": "compressor", "on": True}) if t == 20.0
           else (tr.control({"fault": "compressor", "on": False}) if t == 160.0 else None))
    record("sensor", 60,
           lambda tr, t: tr.control({"fault": "sensor", "on": True}) if t == 20.0
           else (tr.control({"fault": "sensor", "on": False}) if t == 40.0 else None))


if __name__ == "__main__":
    main()
