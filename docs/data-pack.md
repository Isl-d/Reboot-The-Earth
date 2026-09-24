# The data pack and the fleet simulator

Everything the data lane owns. Every file carries a `source` column or property,
so you always know whether a number is real open data or an approximation.
For the rest of the repository, see [file-map.md](file-map.md).
See the [README](../README.md) for the project as a whole.

## What's inside

| File | What it is | Source |
| --- | --- | --- |
| `data/products.csv` | Rules per product: ideal temperature, shelf life, Q10, alert limit, minimum freshness on arrival, value per kg | Storage guidance (USDA Agriculture Handbook 66) + demo assumptions — calibrate with pilot data. Values per kg are placeholders. |
| `data/places.csv` | Port, border crossing, cold warehouse, cold store, supermarkets, food-bank partner | Approximate area locations; real supermarkets added from OpenStreetMap when you run the fetch |
| `data/routes.geojson` | 6 truck routes around Qatar, with distance and duration | Approximate straight segments; real road geometry from OSRM when you run the fetch |
| `data/heat_by_hour.csv` | Outside air temperature, humidity and a 0–100 heat-risk score per route per hour, next 48 h | Synthetic typical-September curve; real Open-Meteo forecast when you run the fetch |
| `data/dispatch_suggestions.csv` | Best and worst departure time per route (05:00–20:00) and freshness saved at loading | Computed from the heat data |
| `scripts/places.py` | Place list, route list and the 12-truck fleet (TRK-07 = the real NodeMCU sensor) | — |
| `scripts/build_data.py` | Rebuilds every data file | OSRM, OpenStreetMap (Overpass), Open-Meteo — all free, no account |
| `simulator/sim.py` | 11 virtual trucks publishing over MQTT, with faults you can trigger | — |

**Every data file has a `source` column or property**, so you always know whether a number is real or approximate.

## Step 1 — get the real open data (on a laptop with internet)

```bash
pip install requests paho-mqtt
python scripts/build_data.py            # real data; falls back to approximate per source if a service fails
python scripts/build_data.py --offline  # approximate data only
```

Run it the day before the demo so the heat forecast covers demo day.

## Step 2 — run the simulator

```bash
python simulator/sim.py --broker localhost --demo-speed 10   # needs Mosquitto running
python simulator/sim.py --dry-run --ticks 3     # test without a broker
```

Each truck publishes every 2 s to `coldguard/<truck_id>/telemetry`, in the same format as the NodeMCU plus position:

```json
{"truck_id":"TRK-01","ts":"2026-10-01T13:40:02Z","air_c":2.8,"hum_pct":88,"door_open":false,
 "lat":25.1876,"lon":51.4501,"route_id":"R2","product":"lettuce","qty_kg":1800,"src":"sim"}
```

The same seed (`--seed 7`) gives the same run every time.

## Step 3 — trigger events (from the backend's demo panel, or by hand)

```bash
mosquitto_pub -t coldguard/control/TRK-03 -m '{"fault":"door","on":true}'         # door opens 20 s
mosquitto_pub -t coldguard/control/TRK-03 -m '{"fault":"compressor","on":true}'   # cooling failure
mosquitto_pub -t coldguard/control/TRK-03 -m '{"fault":"compressor","on":false}'  # cooling restored
mosquitto_pub -t coldguard/control/TRK-03 -m '{"fault":"sensor","on":true}'       # sensor fault (-127)
mosquitto_pub -t coldguard/control/TRK-07 -m '{"backup":true}'                    # simulator replaces the real sensor
mosquitto_pub -t coldguard/control/all    -m '{"reset":true}'                     # reset every truck
```

What the judges will see on a simulated truck (tested):

| Event | Behaviour |
| --- | --- |
| Normal | Holds about 0.5 °C above the product's ideal temperature |
| Defrost cycle | Small bump of about 1.5 °C every 10–20 min, recovers by itself |
| Door opening | Rises about 6 °C over 20 s with `door_open: true`, then recovers |
| Compressor failure | Warms toward outside air: about 8 °C after 10 s, 16 °C after 30 s |
| Cooling restored | Back near the setpoint within about 90 s |

## Notes

- Place coordinates are area-level approximations until you run the fetch. Do not present them as exact addresses.
- Heat and freshness numbers without the fetch are **synthetic**; say so if you show them.
- TRK-07 is skipped by the simulator unless backup mode is on, so the real sensor and the simulator never both publish as TRK-07.
