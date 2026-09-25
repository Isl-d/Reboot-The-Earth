"""Build every data file the ColdGuard demo needs.

    python scripts/build_data.py            # try real open data, fall back offline
    python scripts/build_data.py --offline  # approximate data only, no internet

Real sources (free, no account):
  - Road routes:   OSRM public router (OpenStreetMap roads)
  - Supermarkets:  OpenStreetMap via the Overpass API
  - Weather/heat:  Open-Meteo hourly forecast
Outputs go to data/ and every file records where its numbers came from.
"""
import argparse, csv, json, math, os, sys, datetime as dt

sys.path.insert(0, os.path.dirname(__file__))
from places import PLACES, ROUTES  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
UA = {"User-Agent": "ColdGuard-hackathon-demo/1.0"}
AVG_SPEED_KMH = 60          # used when routing is offline
LOADING_WAIT_H = 0.5        # typical dock / loading exposure per trip
CARGO_SETPOINT_C = 2.0
Q10 = 3.0


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- routes
def route_offline(stops):
    """Straight segments between stops, densified to ~0.5 km points."""
    coords, dist = [], 0.0
    for a, b in zip(stops, stops[1:]):
        pa, pb = PLACES[a][2:4], PLACES[b][2:4]
        d = haversine_km(pa, pb) * 1.25          # roads are ~25% longer than straight lines
        n = max(2, int(d / 0.5))
        for i in range(n):
            t = i / n
            coords.append([pa[1] + (pb[1] - pa[1]) * t, pa[0] + (pb[0] - pa[0]) * t])
        dist += d
    last = PLACES[stops[-1]]
    coords.append([last[3], last[2]])
    return coords, dist, dist / AVG_SPEED_KMH * 60, "approximate straight segments"


def route_osrm(stops, requests):
    pts = ";".join(f"{PLACES[s][3]},{PLACES[s][2]}" for s in stops)
    url = f"https://router.project-osrm.org/route/v1/driving/{pts}?overview=full&geometries=geojson"
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    rt = r.json()["routes"][0]
    return rt["geometry"]["coordinates"], rt["distance"] / 1000, rt["duration"] / 60, "OSRM (OpenStreetMap roads)"


def build_routes(requests):
    feats = []
    for rid, name, stops in ROUTES:
        src = None
        if requests:
            try:
                coords, km, mins, src = route_osrm(stops, requests)
            except Exception as e:  # noqa: BLE001
                print(f"  OSRM failed for {rid}: {e}; using offline geometry")
        if not src:
            coords, km, mins, src = route_offline(stops)
        feats.append({"type": "Feature",
                      "properties": {"route_id": rid, "name": name, "stops": stops,
                                     "distance_km": round(km, 1), "duration_min": round(mins),
                                     "source": src},
                      "geometry": {"type": "LineString", "coordinates": [[round(x, 5), round(y, 5)] for x, y in coords]}})
        print(f"  {rid}: {km:.1f} km, {mins:.0f} min ({src})")
    with open(os.path.join(DATA, "routes.geojson"), "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    return feats


# ---------------------------------------------------------------- places / stores
def build_places(requests):
    rows = [{"place_id": k, "name": v[0], "type": v[1], "lat": v[2], "lon": v[3],
             "has_cold_room": v[4], "source": "approximate area location"} for k, v in PLACES.items()]
    if requests:
        try:
            q = ('[out:json][timeout:25];(node["shop"="supermarket"](24.95,51.35,25.45,51.65);'
                 'way["shop"="supermarket"](24.95,51.35,25.45,51.65););out center 40;')
            r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, headers=UA, timeout=40)
            r.raise_for_status()
            n = 0
            for el in r.json()["elements"]:
                name = el.get("tags", {}).get("name")
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                if name and lat:
                    rows.append({"place_id": f"osm_{el['id']}", "name": name, "type": "store",
                                 "lat": round(lat, 5), "lon": round(lon, 5), "has_cold_room": False,
                                 "source": "OpenStreetMap"})
                    n += 1
            print(f"  added {n} real supermarkets from OpenStreetMap")
        except Exception as e:  # noqa: BLE001
            print(f"  Overpass failed: {e}; keeping approximate places only")
    with open(os.path.join(DATA, "places.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"  wrote {len(rows)} places")


# ---------------------------------------------------------------- heat
def synthetic_hourly(start):
    """Typical late-September Doha curve: ~29.5 °C at 02:00, ~40.5 °C at 14:00."""
    out = []
    for i in range(48):
        t = start + dt.timedelta(hours=i)
        temp = 35 + 5.5 * math.cos(2 * math.pi * (t.hour - 14) / 24)
        out.append((t, round(temp, 1), round(55 - 20 * math.cos(2 * math.pi * (t.hour - 14) / 24))))
    return out


def openmeteo_hourly(lat, lon, requests):
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m"
           "&forecast_days=2&timezone=Asia%2FQatar")
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    h = r.json()["hourly"]
    return [(dt.datetime.fromisoformat(t), T, RH)
            for t, T, RH in zip(h["time"], h["temperature_2m"], h["relative_humidity_2m"])]


def loading_loss_hours(ambient_c):
    """Freshness hours lost during a 30-min loading wait (cargo air ~ halfway to ambient)."""
    cargo = (ambient_c + CARGO_SETPOINT_C) / 2
    return LOADING_WAIT_H * (Q10 ** ((cargo - CARGO_SETPOINT_C) / 10) - 1)


def build_heat(feats, requests):
    start = dt.datetime.now().replace(minute=0, second=0, microsecond=0, hour=0)
    heat_rows, dispatch_rows = [], []
    for ft in feats:
        p = ft["properties"]
        coords = ft["geometry"]["coordinates"]
        samples = [coords[int(i * (len(coords) - 1) / 2)] for i in range(3)]   # start, middle, end
        series, src = None, "synthetic typical September curve"
        if requests:
            try:
                per_pt = [openmeteo_hourly(la, lo, requests) for lo, la in samples]
                series = [(per_pt[0][i][0], round(sum(s[i][1] for s in per_pt) / 3, 1),
                           round(sum(s[i][2] for s in per_pt) / 3)) for i in range(len(per_pt[0]))]
                src = "Open-Meteo forecast"
            except Exception as e:  # noqa: BLE001
                print(f"  Open-Meteo failed for {p['route_id']}: {e}; using synthetic curve")
        if not series:
            series = synthetic_hourly(start)
        for t, T, RH in series:
            risk = max(0, min(100, round((T - 25) / 20 * 100)))
            heat_rows.append({"route_id": p["route_id"], "time": t.isoformat(timespec="minutes"),
                              "air_temp_c": T, "humidity_pct": RH, "heat_risk_0_100": risk, "source": src})
        # best departure over the next 24 h: lowest mean temperature across the trip window
        trip_h = max(1, math.ceil(p["duration_min"] / 60 + LOADING_WAIT_H))
        options = []
        for i in range(0, min(24, len(series) - trip_h)):
            if not 5 <= series[i][0].hour <= 20:     # realistic working-hours departures only
                continue
            window = [s[1] for s in series[i:i + trip_h]]
            options.append((sum(window) / len(window), series[i][0], series[i][1]))
        best, worst = min(options), max(options)
        saved_h = loading_loss_hours(worst[2]) - loading_loss_hours(best[2])
        dispatch_rows.append({"route_id": p["route_id"], "route": p["name"],
                              "best_departure": best[1].strftime("%H:%M"), "mean_temp_best_c": round(best[0], 1),
                              "worst_departure": worst[1].strftime("%H:%M"), "mean_temp_worst_c": round(worst[0], 1),
                              "freshness_saved_hours_loading": round(saved_h, 1), "source": src})
    with open(os.path.join(DATA, "heat_by_hour.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(heat_rows[0])); w.writeheader(); w.writerows(heat_rows)
    with open(os.path.join(DATA, "dispatch_suggestions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dispatch_rows[0])); w.writeheader(); w.writerows(dispatch_rows)
    for d in dispatch_rows:
        print(f"  {d['route_id']}: leave {d['best_departure']} ({d['mean_temp_best_c']} °C) "
              f"not {d['worst_departure']} ({d['mean_temp_worst_c']} °C); "
              f"saves ~{d['freshness_saved_hours_loading']} h freshness at loading")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip internet, approximate data only")
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    requests = None
    if not args.offline:
        try:
            import requests as rq
            requests = rq
        except ImportError:
            print("requests not installed; running offline (pip install requests)")
    print("Routes:"); feats = build_routes(requests)
    print("Places:"); build_places(requests)
    print("Heat and dispatch:"); build_heat(feats, requests)
    print("Done. Files in data/")


if __name__ == "__main__":
    main()
