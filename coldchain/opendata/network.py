"""Fetchers for the free public endpoints.

None of these needs an account or an API key. They are written to be run the
day before the event on a laptop with internet, exactly as the project brief
expects, and they fail politely rather than raising when the network is not
there — a blocked host is reported, not retried around.

Every response is written with its source and licence alongside the numbers,
so a figure on the dashboard can be traced back to what produced it.
"""
from __future__ import annotations

import csv
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger("coldchain.opendata")

TIMEOUT = 45
UA = "ColdChain/1.0 (UN Reboot the Earth hackathon; open data fetcher)"

# The demo operates around Doha. Widen the box and the queries follow.
BBOX = {"south": 24.45, "west": 50.75, "north": 26.20, "east": 51.70}


class Blocked(Exception):
    """The host could not be reached, so the caller can say so plainly."""


def _get(url: str, *, data: bytes | None = None,
         headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, data=data,
                                 headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise Blocked(f"{urllib.parse.urlparse(url).netloc}: {exc}") from exc


def _write(path: Path, rows: list[dict[str, Any]],
           fieldnames: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ------------------------------------------------------------- OpenStreetMap
# The places a refrigerated truck actually stops at. `amenity=marketplace` and
# `shop=supermarket` are the delivery ends; `landuse=industrial` with a cold
# storage tag is where it reloads.
OVERPASS_QUERY = """
[out:json][timeout:60];
(
  node["harbour"="yes"]({s},{w},{n},{e});
  way["harbour"="yes"]({s},{w},{n},{e});
  node["shop"="supermarket"]({s},{w},{n},{e});
  way["shop"="supermarket"]({s},{w},{n},{e});
  node["amenity"="marketplace"]({s},{w},{n},{e});
  node["building"="warehouse"]({s},{w},{n},{e});
  way["building"="warehouse"]({s},{w},{n},{e});
  node["industrial"="warehouse"]({s},{w},{n},{e});
  node["amenity"="fuel"]({s},{w},{n},{e});
  node["amenity"="food_bank"]({s},{w},{n},{e});
  node["social_facility"="food_bank"]({s},{w},{n},{e});
);
out center tags;
"""


def fetch_osm_sites(out: Path) -> dict[str, Any]:
    q = OVERPASS_QUERY.format(s=BBOX["south"], w=BBOX["west"],
                              n=BBOX["north"], e=BBOX["east"])
    raw = _get("https://overpass-api.de/api/interpreter",
               data=urllib.parse.urlencode({"data": q}).encode())
    payload = json.loads(raw)

    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        rows.append({
            "osmId": f"{el.get('type')}/{el.get('id')}",
            "name": tags.get("name") or tags.get("name:en") or "",
            "kind": (tags.get("shop") or tags.get("amenity")
                     or tags.get("building") or tags.get("harbour")
                     or tags.get("social_facility") or "unknown"),
            "latitude": round(float(lat), 6),
            "longitude": round(float(lon), 6),
            "hasColdRoom": "unknown",     # OSM rarely tags this; survey needed
            "source": "OpenStreetMap contributors (ODbL 1.0) via Overpass",
        })
    n = _write(out, rows, ["osmId", "name", "kind", "latitude", "longitude",
                           "hasColdRoom", "source"])
    return {"ok": True, "rows": n}


def fetch_osm_hgv_restrictions(out: Path) -> dict[str, Any]:
    """Weight and height limits: a loaded reefer cannot take every shortcut."""
    q = f"""
    [out:json][timeout:60];
    (
      way["maxweight"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
      way["maxheight"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
      way["hgv"="no"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
    );
    out center tags;
    """
    payload = json.loads(_get("https://overpass-api.de/api/interpreter",
                              data=urllib.parse.urlencode({"data": q}).encode()))
    rows = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        c = el.get("center") or {}
        rows.append({
            "osmId": f"{el.get('type')}/{el.get('id')}",
            "name": tags.get("name", ""),
            "maxWeightT": tags.get("maxweight", ""),
            "maxHeightM": tags.get("maxheight", ""),
            "hgvAccess": tags.get("hgv", ""),
            "latitude": c.get("lat", ""),
            "longitude": c.get("lon", ""),
            "source": "OpenStreetMap contributors (ODbL 1.0) via Overpass",
        })
    n = _write(out, rows, ["osmId", "name", "maxWeightT", "maxHeightM",
                           "hgvAccess", "latitude", "longitude", "source"])
    return {"ok": True, "rows": n}


# ---------------------------------------------------------------- routing
def fetch_routes(out: Path, legs: list[dict[str, Any]]) -> dict[str, Any]:
    """Real road geometry between each pair of stops, from OSRM."""
    features = []
    for leg in legs:
        coords = f"{leg['fromLon']},{leg['fromLat']};{leg['toLon']},{leg['toLat']}"
        url = (f"https://router.project-osrm.org/route/v1/driving/{coords}"
               f"?overview=full&geometries=geojson")
        payload = json.loads(_get(url))
        if not payload.get("routes"):
            log.warning("no route for %s", leg.get("id"))
            continue
        route = payload["routes"][0]
        features.append({
            "type": "Feature",
            "properties": {
                "routeId": leg.get("id"),
                "name": leg.get("name", ""),
                "originId": leg.get("fromId"),
                "destinationId": leg.get("toId"),
                "distanceKm": round(route["distance"] / 1000.0, 3),
                "durationMin": round(route["duration"] / 60.0, 1),
                "source": "OSRM over OpenStreetMap contributors (ODbL 1.0)",
            },
            "geometry": route["geometry"],
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection",
                               "features": features}, indent=1))
    return {"ok": True, "rows": len(features)}


# ---------------------------------------------------------------- weather
def fetch_weather_forecast(out: Path, points: list[dict[str, Any]]) -> dict[str, Any]:
    """Ambient temperature and humidity: the heat load the reefer fights."""
    rows = []
    for p in points:
        url = ("https://api.open-meteo.com/v1/forecast"
               f"?latitude={p['latitude']}&longitude={p['longitude']}"
               "&hourly=temperature_2m,relative_humidity_2m,"
               "shortwave_radiation,apparent_temperature"
               "&forecast_days=7&timezone=UTC")
        payload = json.loads(_get(url))
        h = payload.get("hourly", {})
        for i, t in enumerate(h.get("time", [])):
            rows.append({
                "pointId": p.get("id", ""),
                "time": t,
                "airTempC": h["temperature_2m"][i],
                "relativeHumidityPct": h["relative_humidity_2m"][i],
                "apparentTempC": h["apparent_temperature"][i],
                "solarWM2": h["shortwave_radiation"][i],
                "source": "Open-Meteo (CC BY 4.0)",
            })
    n = _write(out, rows, ["pointId", "time", "airTempC",
                           "relativeHumidityPct", "apparentTempC", "solarWM2",
                           "source"])
    return {"ok": True, "rows": n}


def fetch_weather_history(out: Path, points: list[dict[str, Any]], *,
                          days: int = 365) -> dict[str, Any]:
    """A year of past ambient, so the heat model is calibrated not guessed."""
    end = date.today() - timedelta(days=5)      # the archive lags a few days
    start = end - timedelta(days=days)
    rows = []
    for p in points:
        url = ("https://archive-api.open-meteo.com/v1/archive"
               f"?latitude={p['latitude']}&longitude={p['longitude']}"
               f"&start_date={start.isoformat()}&end_date={end.isoformat()}"
               "&daily=temperature_2m_max,temperature_2m_min,"
               "relative_humidity_2m_mean&timezone=UTC")
        payload = json.loads(_get(url))
        d = payload.get("daily", {})
        for i, day in enumerate(d.get("time", [])):
            rows.append({
                "pointId": p.get("id", ""),
                "date": day,
                "maxTempC": d["temperature_2m_max"][i],
                "minTempC": d["temperature_2m_min"][i],
                "meanRhPct": d.get("relative_humidity_2m_mean", [None] * (i + 1))[i],
                "source": "Open-Meteo archive / ERA5 (CC BY 4.0)",
            })
    n = _write(out, rows, ["pointId", "date", "maxTempC", "minTempC",
                           "meanRhPct", "source"])
    return {"ok": True, "rows": n}


NETWORK_FETCHERS = {
    "osm_cold_sites": fetch_osm_sites,
    "osm_hgv_restrictions": fetch_osm_hgv_restrictions,
    "osrm_routes": fetch_routes,
    "open_meteo_forecast": fetch_weather_forecast,
    "open_meteo_archive": fetch_weather_history,
}
