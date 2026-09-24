"""The demo world: trucks, batches, warehouses, stores and routes.

Coordinates are real places in and around Doha. Distances are computed from
the coordinates rather than typed in, so the numbers stay consistent if a
coordinate is corrected.

This module is plain data with no imports from the rest of the platform, so
the simulator, the seeder and the tests can all share one definition.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    r = 6371.0088
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    lat: float
    lon: float


WAREHOUSES: list[dict] = [
    # id, name, lat, lon, capacity, available, min/max temp
    dict(id="WH01", name="Central Warehouse - Industrial Area", latitude=25.2100,
         longitude=51.4400, capacity_kg=2000, available_capacity_kg=1200,
         min_temp_c=0, max_temp_c=4),
    dict(id="WH02", name="North Cold Store - Al Khor", latitude=25.6800,
         longitude=51.4980, capacity_kg=1500, available_capacity_kg=900,
         min_temp_c=0, max_temp_c=4),
    dict(id="WH03", name="West Depot - Al Rayyan", latitude=25.2920,
         longitude=51.4240, capacity_kg=1200, available_capacity_kg=300,
         min_temp_c=0, max_temp_c=6),
]

STORES: list[dict] = [
    dict(id="ST01", name="Hypermarket - Doha Festival City", latitude=25.3480, longitude=51.4940),
    dict(id="ST02", name="Hypermarket - Al Wakrah", latitude=25.1710, longitude=51.6030),
    dict(id="ST03", name="Hypermarket - Lusail", latitude=25.4300, longitude=51.4900),
    dict(id="ST04", name="Supermarket - Al Sadd", latitude=25.2800, longitude=51.4900),
]

PRODUCTS: list[dict] = [
    dict(id="CHICKEN", name="Fresh Chicken", safe_min_temp_c=0, safe_max_temp_c=4,
         shelf_life_hours=168, value_qar_per_kg=20),
    dict(id="MILK", name="Fresh Milk", safe_min_temp_c=1, safe_max_temp_c=6,
         shelf_life_hours=240, value_qar_per_kg=6),
    dict(id="FISH", name="Fresh Fish", safe_min_temp_c=0, safe_max_temp_c=2,
         shelf_life_hours=72, value_qar_per_kg=35),
    dict(id="LETTUCE", name="Lettuce", safe_min_temp_c=0, safe_max_temp_c=8,
         shelf_life_hours=240, value_qar_per_kg=10),
]

# Every truck carries one batch for the demo. T102 is the headline truck the
# brief uses in every example, so it carries the chicken.
BATCHES: list[dict] = [
    dict(id="CHK-1029", product_id="CHICKEN", quantity_kg=500,
         production_date="2026-09-21", expiry_date="2026-09-28",
         safe_min_temp_c=0, safe_max_temp_c=4, initial_shelf_life_hours=168,
         truck_id="T102"),
    dict(id="MLK-0292", product_id="MILK", quantity_kg=800,
         production_date="2026-09-22", expiry_date="2026-09-30",
         safe_min_temp_c=1, safe_max_temp_c=6, initial_shelf_life_hours=240,
         truck_id="T103"),
    dict(id="FSH-0193", product_id="FISH", quantity_kg=200,
         production_date="2026-09-23", expiry_date="2026-09-26",
         safe_min_temp_c=0, safe_max_temp_c=2, initial_shelf_life_hours=72,
         truck_id="T104"),
    dict(id="LET-0451", product_id="LETTUCE", quantity_kg=1800,
         production_date="2026-09-22", expiry_date="2026-10-02",
         safe_min_temp_c=0, safe_max_temp_c=8, initial_shelf_life_hours=240,
         truck_id="T105"),
    dict(id="CHK-1030", product_id="CHICKEN", quantity_kg=650,
         production_date="2026-09-22", expiry_date="2026-09-29",
         safe_min_temp_c=0, safe_max_temp_c=4, initial_shelf_life_hours=168,
         truck_id="T106"),
]

# Each route is origin -> destination with a handful of waypoints. The
# simulator walks the polyline; the API serves it to the map.
ROUTES: list[dict] = [
    dict(id="R1", name="Hamad Port to Central Warehouse", origin_id="PORT",
         destination_id="WH01",
         geometry=[[51.6050, 25.0000], [51.5500, 25.0900], [51.4900, 25.1600],
                   [51.4400, 25.2100]]),
    dict(id="R2", name="Central Warehouse to Al Wakrah", origin_id="WH01",
         destination_id="ST02",
         geometry=[[51.4400, 25.2100], [51.5100, 25.1900], [51.6030, 25.1710]]),
    dict(id="R3", name="Central Warehouse to Lusail", origin_id="WH01",
         destination_id="ST03",
         geometry=[[51.4400, 25.2100], [51.4700, 25.3200], [51.4900, 25.4300]]),
    dict(id="R4", name="Central Warehouse to Festival City", origin_id="WH01",
         destination_id="ST01",
         geometry=[[51.4400, 25.2100], [51.4700, 25.2900], [51.4940, 25.3480]]),
    dict(id="R5", name="Central Warehouse to Al Sadd", origin_id="WH01",
         destination_id="ST04",
         geometry=[[51.4400, 25.2100], [51.4650, 25.2450], [51.4900, 25.2800]]),
]

# truck id, plate, route, batch
TRUCKS: list[dict] = [
    dict(id="T102", plate="QA-41202", route_id="R1", batch_id="CHK-1029", destination_id="WH01"),
    dict(id="T103", plate="QA-41203", route_id="R2", batch_id="MLK-0292", destination_id="ST02"),
    dict(id="T104", plate="QA-41204", route_id="R3", batch_id="FSH-0193", destination_id="ST03"),
    dict(id="T105", plate="QA-41205", route_id="R4", batch_id="LET-0451", destination_id="ST01"),
    dict(id="T106", plate="QA-41206", route_id="R5", batch_id="CHK-1030", destination_id="ST04"),
]

PORT = Place("PORT", "Hamad Port", 25.0000, 51.6050)


def place_by_id(pid: str) -> Place | None:
    for w in WAREHOUSES:
        if w["id"] == pid:
            return Place(w["id"], w["name"], w["latitude"], w["longitude"])
    for s in STORES:
        if s["id"] == pid:
            return Place(s["id"], s["name"], s["latitude"], s["longitude"])
    return PORT if pid == PORT.id else None


def route_by_id(rid: str) -> dict | None:
    return next((r for r in ROUTES if r["id"] == rid), None)


def route_length_km(route: dict) -> float:
    g = route["geometry"]
    return sum(haversine_km(g[i][1], g[i][0], g[i + 1][1], g[i + 1][0])
               for i in range(len(g) - 1))


def batch_for_truck(truck_id: str) -> dict | None:
    return next((b for b in BATCHES if b["truck_id"] == truck_id), None)


def product_by_id(pid: str) -> dict | None:
    return next((p for p in PRODUCTS if p["id"] == pid), None)


def device_id(truck_id: str) -> str:
    return f"TRUCK-{truck_id}"
