# ColdChain Data Platform — Person 3

Sensors in, operational data out. This service owns the whole path from a
device reading to the JSON the dashboard renders:

```
sensor simulator ─→ MQTT ─→ consumer ─→ validate ─→ normalize ─→ derive
                                                                   │
                                          PostgreSQL / TimescaleDB ┤
                                          Redis (latest state)     ┤
                                                                   ▼
                                                   REST  ·  WebSocket /ws/live
```

## What this service does not do

It never predicts. No spoilage probability, no remaining shelf life, no risk
score and no choice of destination is computed here — those belong to
Person 4's model. `riskLevel` reads `UNKNOWN` and `riskScore` is `null` until
a prediction is posted to `/api/internal/predictions`, at which point this
service stores it, caches it and forwards it unchanged.

The line is deliberate and it is worth stating on stage: everything this
service reports is either measured or arithmetic over measurements.

## Run it

**With Docker** — Mosquitto, TimescaleDB, Redis and the API:

```bash
cd coldchain
docker compose up -d
curl -X POST localhost:8100/api/simulation/start -H 'content-type: application/json' -d '{"speedMultiplier": 1}'
curl localhost:8100/api/trucks | head
```

**On a bare laptop** — no broker, no database, no Docker. The simulator feeds
the pipeline directly, Postgres falls back to SQLite and Redis falls back to
process memory:

```bash
pip install -r coldchain/requirements.txt
python -m coldchain.api.main          # http://localhost:8100
```

`GET /api/health` always says which of those paths is live:

```json
{"status":"ok","database":"postgresql","timescale":true,"cache":"redis",
 "mqtt":{"connected":true,"messages":1420},
 "simulation":{"running":true,"ticks":710,"sink":"mqtt"}}
```

## Telemetry

Published every 2 s (configurable) to `coldchain/trucks/{truckId}/telemetry`:

```json
{
  "deviceId": "TRUCK-T102", "truckId": "T102",
  "timestamp": "2026-09-24T18:25:00Z",
  "temperatureC": 7.2, "humidityPct": 74,
  "latitude": 25.2854, "longitude": 51.5310,
  "speedKmh": 42, "gForce": 0.2,
  "doorOpen": false, "refrigerationOn": true
}
```

`humidityPct` may be **null**: a device that reports no humidity gets none
invented for it, because 0 % is physically implausible in a refrigerated box
and would plot as a real measurement.

Ingest also accepts the shorter spelling from the brief's MQTT example
(`temperature`, `humidity`, `lat`, `lon`) and recovers a missing `truckId`
from the `deviceId` or the topic. A topic that contradicts the payload is a
conflict, not something to guess at.

## Device events

The brief names `coldchain/trucks/{truckId}/events` but does not define its
payload, **so this contract is ours** — say so if a teammate asks, and change
it freely:

```json
{"deviceId": "TRUCK-T102", "truckId": "T102",
 "timestamp": "2026-09-25T09:00:00Z",
 "type": "DOOR_OPENED", "detail": "lid lifted", "value": null}
```

Types: `DOOR_OPENED`, `DOOR_CLOSED`, `REFRIGERATION_ON`, `REFRIGERATION_OFF`,
`SHOCK`, `POWER_LOST`, `POWER_RESTORED`, `SENSOR_FAULT`. Anything else is
rejected with a reason rather than stored — a type the dashboard cannot render
is not useful data.

It exists because telemetry only arrives every 2–5 s, while a door opening is
what *explains* the reading that follows it. An event updates the door and
refrigeration flags the instant it lands, and the next reading carries the
same fields and overwrites them, so telemetry stays authoritative.

Events deliberately do **not** open incidents. Thresholds are accumulated from
the telemetry stream, whose timestamps are regular; an event says a thing
happened, not for how long, and driving a duration threshold from one would be
inventing a number. They are stored in `device_events`, served by
`GET /api/trucks/{id}/events` and `GET /api/device-events`, and pushed on the
WebSocket as `DEVICE_EVENT`.

The simulator publishes them on transitions only — a door that just opened, a
unit that just tripped — not once per tick.

## Scenarios

| Scenario | What it does |
| --- | --- |
| `NORMAL` | Oscillates inside the product's safe band |
| `TEMPERATURE_EXCURSION` | Creeps past the safe maximum and stays there |
| `DOOR_LEFT_OPEN` | Door reported open, humidity climbs, temperature drifts up |
| `REFRIGERATION_FAILURE` | Cooling off, temperature rises towards 41 °C |
| `TRAFFIC_DELAY` | Speed collapses, ETA grows, cooling still works |
| `COMBINED_FAILURE` | Stopped in traffic with the cooling dead |

```bash
curl -X POST localhost:8100/api/simulation/scenario \
  -H 'content-type: application/json' \
  -d '{"truckId":"T102","scenario":"REFRIGERATION_FAILURE","speedMultiplier":10}'
```

## REST

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Which backends are live, message counts, simulation state |
| `GET /api/trucks` · `GET /api/trucks/{id}` | Fleet and one truck, with derived values |
| `GET /api/trucks/{id}/telemetry` | Readings for the charts, oldest first, from the store |
| `GET /api/warehouses` · `/{id}` · `GET /api/stores` · `GET /api/routes` | Map geometry |
| `GET /api/inventory` · `/{batchId}` | Batches, quantities and expiry |
| `GET /api/incidents` · `/{id}` | Threshold incidents, filterable by status |
| `GET /api/trucks/{id}/events` · `GET /api/device-events` | Device events |
| `GET /api/rejected` | Validation failures — bad data is visible, not dropped |
| `POST /api/simulation/start · stop · reset · scenario · tick` | Demo control |
| `GET /api/simulation/runs` | Recorded runs, newest first |
| `GET /api/internal/context/{truckId}` | The bundle Person 4's model consumes |
| `POST /api/internal/predictions · recommendations` | Person 4's output, stored and forwarded |

## WebSocket

`/ws/live` opens with a `HELLO` carrying the whole fleet, then streams:

```json
{"event":"TRUCK_STATE_UPDATED","truckId":"T102","temperatureC":7.5,
 "latitude":25.2858,"longitude":51.5315,"riskScore":78,"riskLevel":"HIGH"}
```

Events: `HELLO`, `TRUCK_STATE_UPDATED`, `INCIDENT_CREATED`,
`INCIDENT_UPDATED`, `DEVICE_EVENT`, `PREDICTION_UPDATED`,
`RECOMMENDATION_UPDATED`, `SIMULATION_RESET`.

Ingest runs on the MQTT thread and sends happen on the asyncio loop, so the
hub hands messages across with `call_soon_threadsafe` and drops a frame rather
than stalling ingest behind a slow client.

## History, and what survives a restart

The pipeline keeps a live window of the last `WINDOW_SIZE` readings per truck.
That buffer is for derived values and the Person 4 bundle; it is capped, and
it dies with the process. Anything a chart plots comes from `sensor_readings`
instead, which is the authoritative record:

* `GET /api/trucks/{id}/telemetry` reads the store and says
  `"source": "database"`. It falls back to the live window (and says
  `"memory"`) when the store is unreachable, and `?source=memory` forces that.
* Open incidents are reloaded at startup, so killing the service mid-excursion
  does not empty the incident panel or let the next reading open a duplicate.
* The fleet is rehydrated from Redis at startup — that is what the cache is
  for. Without it `GET /api/trucks` reports nulls for every field until the
  next reading arrives, which on stage is a blank map. Only measured fields
  come back; derived values start clean, because they are accumulations over
  a stream this process has not seen and restoring them would be a fiction.
  Cached payloads are validated through the model, so a corrupt entry is
  skipped rather than putting a string where the dashboard expects a number.
* A run left open by a process that died is closed at the newest reading in
  the store, not at `now`, so its duration is not inflated by the downtime.
* `POST /api/simulation/reset` empties `sensor_readings`, `device_events`,
  `incidents` and `rejected_readings`. Reset rewinds the simulated clock, so
  rows written before it carry timestamps in the future, and the chart — which
  takes the newest rows by `ts` — would keep serving them and appear frozen.
  Reference data is untouched.

## Open data

Everything this platform runs on is openly licensed, catalogued in
`data/SOURCES.md` and served live from `GET /api/opendata` so the licence
position is checkable from the running system. Seventeen sources across
geography, routing, weather, food science, emissions, physics and operations;
five more are named as deliberately excluded because they are not openly
licensed.

```bash
python -m coldchain.opendata.fetch --list     # the catalogue and its licences
python -m coldchain.opendata.fetch            # collect everything reachable
python -m coldchain.opendata.fetch --offline  # no network attempts
```

Four sources need no network at all — they ship inside open-source packages or
are computed from published formulae, so they work on a stage with no
internet: GeoNames places, public holidays, a psychrometric dew-point table,
and the product storage reference. The rest are free public endpoints with no
account and no API key, fetched the day before the event.

`data/provenance.json` records what actually arrived, when, how many rows and
under what licence. A blocked host is recorded as blocked rather than quietly
skipped, so nothing looks fetched when it was not.

**One caveat worth repeating:** every row of `product_reference.csv` carries
`verified=no`. Those are transcribed literature values with citations to check
them against, present so the platform runs offline — not values any machine
here downloaded. Do not present one to a judge as sourced.

### Condensation

The psychrometrics are load-bearing, not decoration. Each reading carries a
`dewPointC`, and `condensationRisk` is true when the door is open and the dew
point of the incoming air is above the product's safe maximum — warm humid
Gulf air meeting a chilled pallet wets the cartons, and wet cardboard grows
mould long before temperature alone would have spoiled the load. It is null
when the device reports no humidity, because a dew point without one would be
invented.

## Reference data

`fleet.py` defines the demo world and seeds it. After that the database is the
authoritative copy, because some of it changes: a warehouse's available
capacity moves as stock does, and that is the column Person 4 picks a
destination by. `/api/warehouses`, `/api/stores` and `/api/inventory` read the
tables and report `"source": "database"`; they fall back to `fleet.py` (and
say `"fallback"`) when the store is empty or unreachable, so the API still
answers on a laptop with nothing installed. The `candidateWarehouses` in the
Person 4 bundle carries the live capacity for the same reason.

## Migrations

`create_all` is how the demo comes up from nothing. Once teammates have data
they care about, change the schema with Alembic instead:

```bash
python -m alembic -c coldchain/alembic.ini revision --autogenerate -m "what changed"
python -m alembic -c coldchain/alembic.ini upgrade head
```

The URL comes from `COLDCHAIN_DATABASE_URL`, not from `alembic.ini`. A test
builds a database from the migration alone and fails if it has drifted from
the models.

## Derived values

Computed per truck on every accepted reading: step and trip distance
(haversine), temperature deviation, time above the batch's safe maximum,
thermal exposure `E_T = Σ max(0, Tᵢ − T_safe)·Δt` in °C·min, door-open
duration, refrigeration-off duration, distance to destination and ETA. A
stationary truck still gets an ETA — it falls back to a cruising speed rather
than reporting infinity.

## Incidents

Threshold facts, not predictions. `TEMPERATURE_EXCURSION` after 60 s above the
batch's safe maximum, `DOOR_LEFT_OPEN` after 120 s, `REFRIGERATION_FAILURE`
after 60 s with the unit reported off, `SHOCK` above 2 g. One incident stays
open per kind per truck and closes when the condition clears. Every threshold
is in `config.py`.

## One clock

When the simulation runs accelerated, timestamps, accumulated durations and
the `now` that validation compares against all come from one simulated clock
(`clock.py`). Without that, a demo at ×10 would emit ten minutes of readings
carrying the same wall-clock second and no duration-based incident would ever
open. At ×1 the clock tracks real time, so a separate ingest process sees no
skew.

The simulated clock exists **only while the simulation is driving time** — it
is taken on `start()` or on the first hand-driven tick, and given back on
`stop()` or `reset()`. Holding it for the life of the process froze
`clock.now()`, so an idle service rejected a real device's correctly-stamped
telemetry as `timestamp_in_future` once uptime passed the skew limit. The
hardware path and the simulated one share this clock, so releasing it matters
as much as installing it.

## Data quality

Rejected with a reason and logged to `rejected_readings`, never silently
dropped: a temperature outside −40…80 °C (which catches the classic `-127`
from a dead sensor), humidity outside 0–100, latitude or longitude off the
globe, negative speed or g-force, a timestamp from the future or more than a
day old, and a payload with no recoverable truck id.

## Tests

```bash
pytest coldchain/tests -q                        # SQLite + in-memory cache
COLDCHAIN_TEST_DATABASE_URL=postgresql+psycopg://coldchain:coldchain@localhost:5432/coldchain \
  pytest coldchain/tests -q                      # the same suite on Postgres
mosquitto -c coldchain/mosquitto/mosquitto.conf  # then the MQTT tests run too
```

The MQTT integration tests skip themselves when no broker is listening, so the
suite still passes on a laptop with nothing installed.

## Relationship to the rest of the repository

This is a self-contained service under `coldchain/`. It does not import from
or modify the existing ColdGuard backend in `backend/`, which has its own
contracts and its own demo; the two can run side by side on different ports
(8000 and 8100).
