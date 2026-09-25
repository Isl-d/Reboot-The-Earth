"""ColdGuard fleet simulator: 11 virtual refrigerated trucks (+ TRK-07 in backup mode).

    python simulator/sim.py --broker localhost        # publish to MQTT
    python simulator/sim.py --dry-run --ticks 5       # print messages, no broker

Publishes every tick to  coldguard/{truck_id}/telemetry  (same format as the NodeMCU):
    {"truck_id","ts","air_c","hum_pct","door_open","lat","lon","route_id","product","src":"sim"}

Control topic  coldguard/control/{truck_id}  (JSON), e.g.
    {"fault": "door", "on": true}        door opened (auto-closes after 20 s)
    {"fault": "compressor", "on": true}  cooling failure: warms toward outside air
    {"fault": "compressor", "on": false} cooling restored
    {"fault": "sensor", "on": true}      sensor fault (-127 readings)
    {"backup": true}                     only for TRK-07: simulator takes over the real sensor
    {"reset": true}                      topic coldguard/control/all: reset every truck
"""
import argparse, csv, json, math, os, random, sys, time, datetime as dt

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from places import FLEET, REAL_TRUCK  # noqa: E402

DATA = os.path.join(ROOT, "data")


def load_routes():
    with open(os.path.join(DATA, "routes.geojson")) as f:
        fc = json.load(f)
    routes = {}
    for ft in fc["features"]:
        coords = ft["geometry"]["coordinates"]
        seg = [0.0]
        for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
            seg.append(seg[-1] + math.hypot(x2 - x1, y2 - y1))
        routes[ft["properties"]["route_id"]] = {"coords": coords, "cum": seg,
                                                "duration_min": ft["properties"]["duration_min"]}
    return routes


def load_products():
    with open(os.path.join(DATA, "products.csv")) as f:
        return {r["product"]: r for r in csv.DictReader(f)}


def outside_temp_now():
    """Outside air for the current hour from data/heat_by_hour.csv (falls back to 38 °C)."""
    try:
        hour = dt.datetime.now().hour
        with open(os.path.join(DATA, "heat_by_hour.csv")) as f:
            for r in csv.DictReader(f):
                if dt.datetime.fromisoformat(r["time"]).hour == hour:
                    return float(r["air_temp_c"])
    except (OSError, ValueError, KeyError):
        pass
    return 38.0


def point_at(route, frac):
    cum, coords = route["cum"], route["coords"]
    target = frac * cum[-1]
    for i in range(1, len(cum)):
        if cum[i] >= target:
            t = (target - cum[i - 1]) / max(cum[i] - cum[i - 1], 1e-12)
            (x1, y1), (x2, y2) = coords[i - 1], coords[i]
            return y1 + (y2 - y1) * t, x1 + (x2 - x1) * t
    return coords[-1][1], coords[-1][0]


class Truck:
    def __init__(self, tid, route_id, product, qty, start, prod_rules, rng):
        self.id, self.route_id, self.product, self.qty = tid, route_id, product, qty
        self.start, self.rng = start, rng
        self.setpoint = float(prod_rules[product]["ideal_temp_c"]) + 0.5
        self.reset()

    def reset(self):
        self.frac = self.start
        self.air = self.setpoint + self.rng.uniform(-0.5, 0.5)
        self.hum = 88.0
        self.door_until = 0.0
        self.compressor_failed = False
        self.sensor_fault = False
        self.clock = 0.0                      # simulated seconds since reset
        self.next_defrost = self.rng.uniform(120, 600)
        self.defrost_until = 0.0

    def step(self, dt_s, demo_speed, route, outside):
        self.clock += dt_s
        now = self.clock
        # movement: the full route takes duration_min of demo time; loop at the end
        route_s = max(route["duration_min"], 1) * 60
        self.frac = (self.frac + dt_s * demo_speed / route_s) % 1.0
        # temperature physics (per real second, tuned to be visible on stage)
        door_open = now < self.door_until
        if door_open:
            target, rate = outside, 0.01
        elif self.compressor_failed:
            target, rate = outside, 0.015
        elif now < self.defrost_until:
            target, rate = self.setpoint + 1.5, 0.05
        else:
            target, rate = self.setpoint, 0.06
        if now > self.next_defrost and not self.compressor_failed:
            self.defrost_until = now + 40
            self.next_defrost = now + self.rng.uniform(600, 1200)
        self.air += (target - self.air) * min(1.0, rate * dt_s) + self.rng.gauss(0, 0.05)
        self.hum = max(40.0, min(98.0, self.hum + self.rng.gauss(0, 0.3) - (0.2 if door_open else -0.05)))
        lat, lon = point_at(route, self.frac)
        return {
            "truck_id": self.id,
            "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "air_c": -127.0 if self.sensor_fault else round(self.air, 2),
            "hum_pct": round(self.hum),
            "door_open": door_open,
            "lat": round(lat, 5), "lon": round(lon, 5),
            "route_id": self.route_id, "product": self.product, "qty_kg": self.qty,
            "src": "sim",
        }

    def control(self, msg):
        f, on = msg.get("fault"), msg.get("on", True)
        if f == "door":
            self.door_until = self.clock + (20 if on else 0)
        elif f == "compressor":
            self.compressor_failed = bool(on)
        elif f == "sensor":
            self.sensor_fault = bool(on)
        if msg.get("reset"):
            self.reset()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between readings")
    ap.add_argument("--demo-speed", type=float, default=10,
                    help="how fast trucks move along their routes; match the backend's "
                         "MAP_SPEED so all twelve move at one rate. The backend's "
                         "shelf-life clock is separate and runs at x120.")
    ap.add_argument("--dry-run", action="store_true", help="print messages instead of publishing")
    ap.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run forever)")
    ap.add_argument("--seed", type=int, default=7, help="fixed seed so every demo run is identical")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    routes, products = load_routes(), load_products()
    trucks = {tid: Truck(tid, r, p, q, s, products, rng) for tid, r, p, q, s in FLEET}
    backup = {"on": False}      # TRK-07 is simulated only in backup mode

    client = None
    if not args.dry_run:
        import paho.mqtt.client as mqtt

        def on_message(_c, _u, m):
            try:
                msg = json.loads(m.payload or b"{}")
            except json.JSONDecodeError:
                return
            target = m.topic.rsplit("/", 1)[-1]
            if target == "all" and msg.get("reset"):
                for t in trucks.values():
                    t.reset()
                print("reset all trucks")
                return
            if target == REAL_TRUCK and "backup" in msg:
                backup["on"] = bool(msg["backup"])
                print(f"backup mode for {REAL_TRUCK}: {backup['on']}")
            if target in trucks:
                trucks[target].control(msg)
                print(f"control {target}: {msg}")

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="coldguard-sim")
        client.on_message = on_message
        client.connect(args.broker, args.port)
        client.subscribe("coldguard/control/+")
        client.loop_start()
        print(f"simulating {len(trucks) - 1} trucks (+{REAL_TRUCK} in backup mode) -> {args.broker}:{args.port}")

    tick, last = 0, time.time()
    try:
        while True:
            now = time.time()
            dt_s, last = now - last, now
            outside = outside_temp_now()
            for t in trucks.values():
                if t.id == REAL_TRUCK and not backup["on"]:
                    continue
                msg = t.step(dt_s if tick else args.interval, args.demo_speed, routes[t.route_id], outside)
                topic = f"coldguard/{t.id}/telemetry"
                if client:
                    client.publish(topic, json.dumps(msg))
                else:
                    print(topic, json.dumps(msg))
            tick += 1
            if args.ticks and tick >= args.ticks:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.loop_stop()
            client.disconnect()


if __name__ == "__main__":
    main()
