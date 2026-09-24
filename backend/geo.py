"""Places, routes and distances (data/places.csv + data/routes.geojson).

All geometry is open data: OpenStreetMap places and OSRM road shapes after
`python scripts/build_data.py` has run, approximate straight segments before.
Distances are haversine kilometres along the real polyline, so they stay
honest even when the shape is still the approximate one.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from functools import lru_cache

from . import config

EARTH_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    type: str
    lat: float
    lon: float
    has_cold_room: bool
    source: str

    def as_dict(self) -> dict:
        return {"place_id": self.place_id, "name": self.name, "type": self.type,
                "lat": self.lat, "lon": self.lon, "has_cold_room": self.has_cold_room,
                "source": self.source}


@dataclass
class Route:
    route_id: str
    name: str
    stops: list[str]
    coords: list[list[float]]        # [lon, lat] pairs, GeoJSON order
    cum_km: list[float]
    distance_km: float
    duration_min: float
    source: str

    @property
    def total_km(self) -> float:
        return self.cum_km[-1] or self.distance_km

    def point_at(self, frac: float) -> tuple[float, float]:
        """(lat, lon) at `frac` (0..1) of the way along the route."""
        frac = min(max(frac, 0.0), 1.0)
        target = frac * self.total_km
        for i in range(1, len(self.cum_km)):
            if self.cum_km[i] >= target:
                span = max(self.cum_km[i] - self.cum_km[i - 1], 1e-12)
                t = (target - self.cum_km[i - 1]) / span
                (x1, y1), (x2, y2) = self.coords[i - 1], self.coords[i]
                return y1 + (y2 - y1) * t, x1 + (x2 - x1) * t
        return self.coords[-1][1], self.coords[-1][0]

    def frac_of_nearest_point(self, lat: float, lon: float) -> float:
        """Where along the route a given position sits (0..1)."""
        best_i, best_d = 0, float("inf")
        for i, (x, y) in enumerate(self.coords):
            d = haversine_km(lat, lon, y, x)
            if d < best_d:
                best_i, best_d = i, d
        return self.cum_km[best_i] / max(self.total_km, 1e-12)

    def remaining_km(self, frac: float) -> float:
        return max(0.0, (1.0 - min(max(frac, 0.0), 1.0)) * self.total_km)

    def remaining_h(self, frac: float) -> float:
        return self.remaining_km(frac) / max(config.TRUCK_SPEED_KMH, 1e-9)

    def geometry_from(self, frac: float) -> list[list[float]]:
        """The part of the route still ahead, for redrawing on the map."""
        lat, lon = self.point_at(frac)
        target = min(max(frac, 0.0), 1.0) * self.total_km
        tail = [[lon, lat]]
        tail += [c for c, km in zip(self.coords, self.cum_km) if km > target]
        return tail

    @property
    def destination_id(self) -> str:
        return self.stops[-1]


@lru_cache(maxsize=1)
def load_places() -> dict[str, Place]:
    out: dict[str, Place] = {}
    with open(config.DATA_DIR / "places.csv", newline="") as f:
        for r in csv.DictReader(f):
            out[r["place_id"]] = Place(
                place_id=r["place_id"], name=r["name"], type=r["type"],
                lat=float(r["lat"]), lon=float(r["lon"]),
                has_cold_room=str(r["has_cold_room"]).strip().lower() == "true",
                source=r.get("source", ""))
    return out


@lru_cache(maxsize=1)
def load_routes() -> dict[str, Route]:
    with open(config.DATA_DIR / "routes.geojson") as f:
        fc = json.load(f)
    out: dict[str, Route] = {}
    for ft in fc["features"]:
        p = ft["properties"]
        coords = ft["geometry"]["coordinates"]
        cum = [0.0]
        for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
            cum.append(cum[-1] + haversine_km(y1, x1, y2, x2))
        out[p["route_id"]] = Route(
            route_id=p["route_id"], name=p.get("name", p["route_id"]),
            stops=list(p.get("stops", [])), coords=coords, cum_km=cum,
            distance_km=float(p.get("distance_km", cum[-1])),
            duration_min=float(p.get("duration_min", cum[-1])),
            source=p.get("source", ""))
    return out


def nearest_place(lat: float, lon: float, types: tuple[str, ...],
                  cold_only: bool = False) -> tuple[Place, float]:
    """Closest place of the given types, and the road km to it."""
    best, best_km = None, float("inf")
    for pl in load_places().values():
        if pl.type not in types or (cold_only and not pl.has_cold_room):
            continue
        km = haversine_km(lat, lon, pl.lat, pl.lon) * config.ROAD_FACTOR
        if km < best_km:
            best, best_km = pl, km
    if best is None:                      # never happens with the shipped data
        raise LookupError(f"no place of type {types} in data/places.csv")
    return best, best_km


def drive_h(km: float) -> float:
    return km / max(config.TRUCK_SPEED_KMH, 1e-9)
