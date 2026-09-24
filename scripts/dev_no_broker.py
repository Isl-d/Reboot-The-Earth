"""Run the whole demo on one laptop with no broker, no database and no Docker.

    python scripts/dev_no_broker.py            # backend on :8000, fleet running
    python scripts/dev_no_broker.py --script   # plus the four-minute demo, on its own

This is a development harness, not the real path: on stage the NodeMCU and
simulator/sim.py publish over MQTT. It exists so that anyone on the team can
open the dashboard and work on the frontend without installing anything.

It drives the same simulator physics straight into the ingest pipeline, so what
you see is what MQTT would have delivered.
"""
from __future__ import annotations

import argparse
import random
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "simulator"))

from places import FLEET, REAL_TRUCK                      # noqa: E402
from sim import Truck, load_products, load_routes          # noqa: E402

INTERVAL = 2.0
OUTSIDE = 41.0

# The stage script: what the presenter does to the real sensor, minute by
# minute (CLAUDE.md section 8). Each entry is (seconds from start, air °C).
STAGE = [(0, None), (40, "door"), (70, "hand"), (225, "back")]


class Stage:
    """Replays what the physical box does to TRK-07, without the box."""

    def __init__(self) -> None:
        self.t0 = time.time()
        self.air = 2.6

    def air_c(self) -> tuple[float, bool]:
        t = time.time() - self.t0
        if 40 <= t < 46:                       # lid lifted for six seconds
            target, door = 11.0, True
        elif 70 <= t < 225:                    # held in a hand
            target, door = 29.0, False
        else:                                  # back in the cold box
            target, door = 2.6, False
        # A DHT11 is slow: move towards the target rather than jumping.
        self.air += (target - self.air) * 0.22
        return round(self.air, 1), door


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--script", action="store_true",
                    help="also act out the four-minute demo on TRK-07")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import uvicorn
    from backend import config
    import backend.main as main_mod

    main_mod.ingest.start = lambda: None                   # no MQTT in this mode

    rng = random.Random(args.seed)
    routes, products = load_routes(), load_products()
    sim = {tid: Truck(tid, r, p, q, s, products, rng) for tid, r, p, q, s in FLEET}
    stage = Stage() if args.script else None

    def pump() -> None:
        time.sleep(1.5)                                    # let the app start
        print(f"feeding {len(sim)} trucks into the ingest pipeline"
              + (" - demo script running on " + REAL_TRUCK if stage else ""))
        while True:
            for tid, truck in sim.items():
                if tid == REAL_TRUCK:
                    if stage is None:
                        continue
                    air, door = stage.air_c()
                    main_mod.ingest.handle(tid, {"truck_id": tid, "air_c": air,
                                                 "hum_pct": 62, "door_open": door})
                    continue
                msg = truck.step(INTERVAL, config.MAP_SPEED, routes[truck.route_id], OUTSIDE)
                main_mod.ingest.handle(tid, msg)
            time.sleep(INTERVAL)

    threading.Thread(target=pump, name="dev-feed", daemon=True).start()
    print(f"dashboard: run `npm run dev` in web/, then open http://localhost:5173")
    print(f"API:       http://localhost:{args.port}/api/fleet")
    uvicorn.run(main_mod.app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
