"""Drive the four-minute demo against a running platform.

    python coldchain/scripts/demo.py                 # against localhost:8100
    python coldchain/scripts/demo.py --host 10.0.0.5

Starts the simulation, puts T102 into a refrigeration failure, and prints the
temperature, the derived values and the incidents as they appear. Nothing here
computes anything — it reads the API, so what it prints is exactly what a
judge sees on the dashboard.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def get(self, path: str):
        with urllib.request.urlopen(self.base + path, timeout=10) as r:
            return json.loads(r.read())

    def post(self, path: str, body: dict | None = None):
        req = urllib.request.Request(
            self.base + path, data=json.dumps(body or {}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--truck", default="T102")
    ap.add_argument("--scenario", default="REFRIGERATION_FAILURE")
    ap.add_argument("--speed", type=float, default=5.0)
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()

    api = Api(f"http://{args.host}:{args.port}")

    health = api.get("/api/health")
    print(f"db={health['database']} cache={health['cache']} "
          f"mqtt={health['mqtt']['connected']} sink={health['simulation']['sink']}")

    api.post("/api/simulation/reset")
    api.post("/api/simulation/start", {"speedMultiplier": args.speed})
    api.post("/api/simulation/scenario",
             {"truckId": args.truck, "scenario": args.scenario})
    print(f"\n{args.truck} -> {args.scenario} at x{args.speed}\n")
    print(f"{'time':>5}  {'temp':>6}  {'fridge':>6}  {'exposure':>9}  "
          f"{'above':>7}  {'eta':>6}  incidents")

    seen: set[str] = set()
    start = time.time()
    while time.time() - start < args.seconds:
        try:
            t = api.get(f"/api/trucks/{args.truck}")
            incidents = api.get("/api/incidents")["incidents"]
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  api unreachable: {exc}")
            time.sleep(2)
            continue

        d = t["derived"]
        print(f"{time.time() - start:5.0f}  {str(t['temperatureC']):>6}  "
              f"{str(t['refrigerationOn']):>6}  {d['thermalExposureCMin']:9.1f}  "
              f"{d['timeAboveThresholdS']:7.0f}  "
              f"{'-' if d['etaMinutes'] is None else format(d['etaMinutes'], '.0f'):>6}  "
              f"{len(incidents)}")

        for inc in incidents:
            if inc["id"] not in seen:
                seen.add(inc["id"])
                print(f"       ! {inc['id']} {inc['type']} "
                      f"{inc['severity']} - {inc['detail']}")
        time.sleep(2)

    api.post("/api/simulation/stop")
    print("\nstopped. rejected readings:",
          api.get("/api/health")["rejectedReadings"])


if __name__ == "__main__":
    main()
