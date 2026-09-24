"""Shared place and route definitions for the ColdGuard demo.

Coordinates are APPROXIMATE (area level). Run scripts/fetch_open_data.py on a
laptop with internet to replace routes with real road geometry (OSRM) and add
real supermarket locations (OpenStreetMap).
"""

PLACES = {
    # id: (name, type, lat, lon, has_cold_room)
    "hamad_port":     ("Hamad Port", "port", 25.000, 51.605, False),
    "abu_samra":      ("Abu Samra border crossing", "border", 24.750, 50.840, False),
    "wh_industrial":  ("Cold warehouse - Industrial Area", "warehouse", 25.190, 51.430, True),
    "cs_wakrah":      ("Cold store - Al Wakrah", "cold_store", 25.160, 51.590, True),
    "store_wakrah":   ("Supermarket - Al Wakrah", "store", 25.170, 51.600, False),
    "store_doha":     ("Supermarket - Central Doha", "store", 25.285, 51.530, False),
    "store_lusail":   ("Supermarket - Lusail", "store", 25.420, 51.490, False),
    "store_khor":     ("Supermarket - Al Khor", "store", 25.680, 51.500, False),
    "store_rayyan":   ("Supermarket - Al Rayyan", "store", 25.290, 51.420, False),
    "foodbank_doha":  ("Food bank partner - Doha", "food_bank", 25.270, 51.510, True),
}

# Each route: id, name, ordered list of place ids (start, [via...], end)
ROUTES = [
    ("R1", "Hamad Port to Industrial Area warehouse", ["hamad_port", "cs_wakrah", "wh_industrial"]),
    ("R2", "Industrial Area warehouse to Al Wakrah", ["wh_industrial", "store_wakrah"]),
    ("R3", "Industrial Area warehouse to Lusail", ["wh_industrial", "store_doha", "store_lusail"]),
    ("R4", "Abu Samra border to Industrial Area warehouse", ["abu_samra", "wh_industrial"]),
    ("R5", "Industrial Area warehouse to Al Khor", ["wh_industrial", "store_lusail", "store_khor"]),
    ("R6", "Industrial Area warehouse to Al Rayyan", ["wh_industrial", "store_rayyan"]),
]

# Fleet: TRK-07 is the real sensor (not simulated unless backup mode is on).
FLEET = [
    # truck_id, route_id, product, qty_kg, start_fraction_along_route
    ("TRK-01", "R2", "lettuce", 1800, 0.10),
    ("TRK-02", "R3", "milk", 2500, 0.30),
    ("TRK-03", "R3", "lettuce", 1500, 0.65),
    ("TRK-04", "R4", "chicken", 3000, 0.20),
    ("TRK-05", "R4", "lettuce", 2200, 0.55),
    ("TRK-06", "R5", "milk", 2000, 0.15),
    ("TRK-07", "R1", "lettuce", 2000, 0.05),   # REAL sensor (NodeMCU + DHT11)
    ("TRK-08", "R5", "chicken", 1200, 0.50),
    ("TRK-09", "R6", "lettuce", 1600, 0.35),
    ("TRK-10", "R6", "milk", 1800, 0.70),
    ("TRK-11", "R2", "chicken", 1400, 0.60),
    ("TRK-12", "R1", "milk", 2400, 0.40),
]
REAL_TRUCK = "TRK-07"
