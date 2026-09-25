# ColdGuard — Project Brief for Claude Code

This file is the single source of truth for the project. Read it fully before writing code.

---

## 1. Context

- **Event:** UN "Reboot the Earth" hackathon at Carnegie Mellon University in Qatar (CMU-Q EcoCampus).
- **Challenge 2:** *AI for Cold-Chain Monitoring and Food-Loss Reduction.* The challenge asks for three features:
  1. **Cold-Chain Data Integration** — combine temperature and humidity readings with product information, location, handling history, and transportation and storage records.
  2. **Spoilage and Shelf-Life Prediction** — use AI to identify cold-chain anomalies, estimate spoilage risk and predict the remaining shelf life of fresh food.
  3. **Smart Alerts and Actions** — timely alerts and recommended actions such as inspecting or rerouting shipments, adjusting storage conditions, or prioritizing products for sale.
- **Why it matters:** about 13% of food is lost between harvest and retail and 19% more is wasted after (FAO/UNEP 2024); food loss and waste cause 8–10% of global emissions. Qatar's National Food Security Strategy 2030 targets −50% food waste and −30% food loss. Gulf summers exceed 45 °C, so a failed truck fridge can spoil food within hours.
- **Goal of the build:** a working proof of concept for judges, including a live hardware demo, in about 48 hours.

## 2. The product in one paragraph

**ColdGuard** gives every pallet of food a live "freshness score". Sensors report temperature; the system tells a real refrigeration failure apart from a door opening; it calculates how many days of freshness are left and whether the food will still be accepted when it arrives; and an AI agent recommends the best action (reroute, sell first, discount, donate), which a person approves with one tap. The demo shows one real sensor (truck **TRK-07**) inside a fleet of 12 trucks on a live map of Doha.

## 3. Hard constraints

- **Everything open source**, and free open data only (OpenStreetMap, OSRM, Open-Meteo, Copernicus/NASA).
- **Runs on one laptop, offline on stage.** No cloud services, no paid APIs, no API keys. The LLM runs locally.
- **The LLM never produces numbers.** All numbers come from deterministic Python (models, rules, planner). The LLM only writes the human explanation from a JSON of facts.
- **A human approves every action.**
- **Demo must be repeatable:** fixed random seed, one-click reset, no terminal commands typed on stage.
- Keep it simple: one backend process, no Kafka, no Kubernetes for the hackathon.

## 4. Hardware we actually have

- **Board:** NodeMCU **ESP8266** (ESP-12 module, micro-USB). Has Wi-Fi, **2.4 GHz only**. (Not an ESP32.)
- **Sensor:** **DHT11** temperature + humidity module (3-pin board with built-in pull-up resistor). Range 0–50 °C, about ±2 °C, slowish response. Not waterproof.
- An unused blue comparator-type sensor module (ignore it).
- Demo rig: small cooler/lunchbox with 2 ice packs; the DHT11 is taped inside the lid so it sits in cold air (never in water). Target resting air temperature below 6 °C.
- Network: phone hotspot or travel router on 2.4 GHz, shared by the NodeMCU and the laptop. Fix the laptop's IP.

### Wiring

| DHT11 pin | NodeMCU pin |
| --- | --- |
| + / VCC | 3V3 |
| − / GND | G (GND) |
| S / OUT / DATA | D2 (GPIO4) |

### Arduino setup

- Arduino IDE 2 → Boards Manager: **"esp8266 by ESP8266 Community"** (URL if missing: `http://arduino.esp8266.com/stable/package_esp8266com_index.json`). Board: **NodeMCU 1.0 (ESP-12E Module)**.
- Libraries: **DHT sensor library** (Adafruit) + **Adafruit Unified Sensor**, **PubSubClient**.
- Use a data-capable USB cable. Install CP210x/CH340 driver if no port appears.

### Firmware (firmware/node/node.ino)

Publishes every 2 s to `coldguard/TRK-07/telemetry`. Improve it with automatic Wi-Fi/MQTT reconnect; optional lid switch → `door_open`.

```cpp
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

const char* WIFI_SSID = "YOUR_HOTSPOT";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* MQTT_HOST = "192.168.1.50";   // laptop IP on the demo network

DHT dht(4, DHT11);                        // data on D2 (GPIO4)
WiFiClient net;
PubSubClient mqtt(net);

void setup() {
  Serial.begin(115200);
  dht.begin();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  mqtt.setServer(MQTT_HOST, 1883);
}

void loop() {
  if (!mqtt.connected()) mqtt.connect("coldguard-node1");
  mqtt.loop();
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  if (isnan(t)) { delay(2000); return; }
  char msg[100];
  snprintf(msg, sizeof(msg), "{\"truck_id\":\"TRK-07\",\"air_c\":%.1f,\"hum_pct\":%.0f}", t, h);
  mqtt.publish("coldguard/TRK-07/telemetry", msg);
  Serial.println(msg);
  delay(2000);
}
```

Alternatives if hardware changes: ESP32 (change include to `<WiFi.h>`), Arduino without Wi-Fi (send over USB serial; a Python bridge publishes to MQTT), Raspberry Pi (read the sensor directly in Python and publish).

## 5. Architecture (hackathon version)

```
NodeMCU (TRK-07) ─┐
                  ├─ MQTT (Mosquitto) ─→ Backend (FastAPI, one Python process) ─→ PostgreSQL
Simulator (11) ───┘                        │  ingest · detector · freshness · planner · agent · audit
                                           ├─→ Ollama (Qwen2.5-7B, local) for explanations
                                           └─→ WebSocket/REST ─→ Dashboard (React + Vite + MapLibre)
```

| Service | Tool | Port |
| --- | --- | --- |
| mosquitto | eclipse-mosquitto (`listener 1883`, `allow_anonymous true`, demo only) | 1883 |
| db | PostgreSQL (TimescaleDB optional) | 5432 |
| backend | Python 3.11, FastAPI, paho-mqtt ≥ 2.0, psycopg | 8000 |
| simulator | Python 3.11 (`simulator/sim.py`, already written) | — |
| ollama | ollama/ollama with `qwen2.5:7b` (pull before the event) | 11434 |
| web | React + Vite + TypeScript + MapLibre GL + OSM tiles | 5173 |

Everything starts with `docker compose up`, except the NodeMCU. The laptop needs about 16 GB RAM for the local LLM.

### Repository layout

```
coldguard/
├── CLAUDE.md                     # this file
├── docker-compose.yml
├── requirements.txt
├── firmware/node/node.ino
├── data/                         # ALREADY BUILT (see section 9)
│   ├── products.csv
│   ├── places.csv
│   ├── routes.geojson
│   ├── heat_by_hour.csv
│   └── dispatch_suggestions.csv
├── scripts/
│   ├── places.py                 # ALREADY BUILT: places, routes, 12-truck fleet
│   └── build_data.py             # ALREADY BUILT: fetches real open data
├── simulator/sim.py              # ALREADY BUILT: 11 virtual trucks + faults
├── backend/
│   ├── config.py      # every threshold, cost and clock, one place
│   ├── main.py        # FastAPI app, REST + WebSocket + /track
│   ├── ingest.py      # MQTT subscriber → validate → DB + in-memory state
│   ├── state.py       # in-memory fleet, product-temperature lag, risk
│   ├── geo.py         # places, routes, distances along the polyline
│   ├── detector.py    # door / defrost / sensor fault / cooling failure
│   ├── freshness.py   # Q10 model, freshness on arrival, risk
│   ├── planner.py     # options A–F, scoring, escalation to a human
│   ├── agent.py       # Qwen2.5 explanation + numeric guard + template fallback
│   ├── audit.py       # hash-chained decision log
│   ├── db.py          # PostgreSQL, degrades to memory only
│   ├── templates/track.html
│   ├── schema.sql · seed.sql · Dockerfile
├── tests/             # 72 tests + recorded simulator traces
├── docs/              # decision-policy.md · data-pack.md
├── pitch/             # DEMO_SCRIPT.md · DECK.md
└── web/src/  Map.tsx · FleetList.tsx · TruckPanel.tsx · AlertCard.tsx · OptionsTable.tsx ·
           EventLog.tsx · DemoPanel.tsx · ComparisonScreen.tsx · DispatchCard.tsx · Sparkline.tsx
```

The QR page is server-rendered by the backend (`backend/templates/track.html`)
rather than a React route, so a phone can open it without loading the dashboard.

## 6. Data contracts (do not change without updating all sides)

**Telemetry** — topic `coldguard/{truck_id}/telemetry`, every 2 s.

- From the NodeMCU (minimal): `{"truck_id":"TRK-07","air_c":3.4,"hum_pct":86}`. The backend adds `ts` (receive time), position (from TRK-07's route R1), product and quantity from the fleet definition, and `src:"esp8266"`.
- From the simulator (full):
  ```json
  {"truck_id":"TRK-01","ts":"2026-10-01T13:40:02Z","air_c":2.8,"hum_pct":88,"door_open":false,
   "lat":25.1876,"lon":51.4501,"route_id":"R2","product":"lettuce","qty_kg":1800,"src":"sim"}
  ```

**Control** — topic `coldguard/control/{truck_id}`, handled by the simulator:
`{"fault":"door","on":true}` (auto-closes after 20 s) · `{"fault":"compressor","on":true|false}` · `{"fault":"sensor","on":true|false}` (sends −127) · `{"backup":true|false}` on TRK-07 only (simulator publishes TRK-07 instead of the real sensor) · `{"reset":true}` on `coldguard/control/all`.

**Database tables**

| Table | Key columns |
| --- | --- |
| products | product, ideal_temp_c, life_at_ideal_days, q10, alert_limit_c, min_life_on_arrival_days, value_qar_per_kg |
| places | place_id, name, type, lat, lon, has_cold_room, source |
| shipments | truck_id, product, qty_kg, route_id, destination_place_id, eta, life_left_h, status |
| readings | ts, truck_id, air_c, hum_pct, door_open, lat, lon, src |
| events | truck_id, type (door, defrost, sensor_fault, failure), started_at, ended_at, peak_c |
| decisions | shipment/truck, options (json), facts (json), chosen, text_ar, text_en, text_source, approved_by, approved_at, prev_hash, hash |

The `readings` table stores the air reading as sent. The cargo temperature is
derived in `state.py` and is not a separate column.

**Backend API**

| Endpoint | Purpose |
| --- | --- |
| `GET /api/fleet` | All trucks: temperature, humidity, freshness, risk, position, totals |
| `GET /api/trucks/{id}` | One truck |
| `GET /api/trucks/{id}/history` | Temperature (air and cargo) and freshness timeline |
| `GET /api/places` · `GET /api/routes` | Reference geometry for the map |
| `GET /api/heat` | Heat-risk layer from `heat_by_hour.csv` |
| `GET /api/dispatch` | Best departure times per route (from `dispatch_suggestions.csv`) |
| `GET /api/events` · `GET /api/decisions` · `GET /api/decisions/{id}` | Log and decisions |
| `GET /api/audit` | Hash chain plus `chain_ok` |
| `GET /api/impact` | Comparison screen: with and without ColdGuard |
| `POST /api/decisions/{id}/approve` | Approve → execute (update route/destination) → audit log |
| `POST /api/demo/fault` | `{truck_id, fault, on}` → publishes to the control topic |
| `POST /api/demo/backup` | Toggle TRK-07 backup mode |
| `POST /api/demo/reset` | Reset state and simulator |
| `WS /ws` | Push `reading`, `event`, `alert`, `decision` messages |
| `GET /track/TRK-07` | Mobile page for the QR code on the cooler box |

## 7. Core logic (deterministic Python)

### 7.1 Product profiles (`data/products.csv`; demo assumptions, calibrate later)

| Product | Ideal °C | Life at ideal | Q10 | Alert limit °C | Min on arrival | Value QAR/kg (placeholder) |
| --- | --- | --- | --- | --- | --- | --- |
| lettuce | 2 | 10 days | 3 | 8 | 6 days | 10 |
| chicken | 2 | 5 days | 3 | 4 | 3 days | 20 |
| milk | 4 | 10 days | 3 | 7 | 6 days | 6 |

### 7.2 Detector (per truck, rolling window)

| Event | Rule (demo value / real-world value) | Result |
| --- | --- | --- |
| Door opening | `door_open` true, or a rise that returns below the limit within 20 s / 10 min | Log "door opening — no action" |
| Defrost | Small bump (< 2 °C) that recovers on its own | Log only |
| Sensor fault | −127, `NaN`, no reading for 10 s, or a jump > 15 °C between readings | "Check sensor" warning; pause freshness |
| Cooling failure | Above the product's alert limit for **30–45 s** (DHT11 is slow) / 10 min, door closed, temperature rising or flat | **Alert** → planner |

### 7.3 Freshness model

```
speed          = Q10 ** ((T - ideal_temp_c) / 10)      # warmer = ages faster
life_left_h   -= dt_hours * DEMO_SPEED * speed         # DEMO_SPEED = 120 (1 s on stage = 2 min)
hours_to_spoil = life_left_h / speed                   # at the current temperature
life_on_arrival_h = life_left_h - remaining_trip_h * speed_on_the_way
at_risk = life_on_arrival_h < min_life_on_arrival_days * 24
```

Two refinements were needed once this met the real sensor. Both are in
`config.py` and both are visible on the dashboard.

**T is the cargo temperature, not the air reading.** A DHT11 spikes in seconds;
two tonnes of lettuce follow with a lag. The product temperature is a
first-order lag on the air reading with a time constant of `PRODUCT_LAG_H`
(2 simulated hours). The detector still watches the air, because that is what
catches a failure early. Without this, one second of a warm hand burned half a
day of shelf life and the demo's own numbers stopped adding up.

**`speed_on_the_way` defaults to 1.0**, which reproduces the plain subtraction
above for a load that is cooling normally. The dashboard assumes a warm spell is
fixed within `WARM_PROJECTION_H` (1 h) — unless the detector has an open cooling
failure, in which case it uses the honest worst case, warm for the whole
remaining trip. A lifted lid therefore never turns the fleet amber, and a
confirmed failure turns it amber at once. The planner always uses the worst case
for option A (section 7.4).

Two clocks, both labelled on screen:

| Clock | Constant | Rate | Drives |
| --- | --- | --- | --- |
| Shelf life | `DEMO_SPEED` | ×120 | Spoilage: 1 s on stage = 2 min |
| Map | `MAP_SPEED` | ×10 | Movement, so a truck crosses its route over the four-minute demo |

Pass the same `--demo-speed 10` to `simulator/sim.py` so all twelve trucks move
at one rate.

### 7.4 Planner (options for an at-risk shipment)

| Option | Verb | Meaning |
| --- | --- | --- |
| A. Continue as planned | continue | Baseline; usually fails the store minimum |
| B. Divert to nearest cold store | reroute | Cooling restored after the drive there; then continue |
| C. Deliver direct to nearest store | reroute | Skip the warehouse; shorter remaining trip |
| D. Sell now with a markdown | sell | Always possible; recovers part of the value |
| E. Donate to the food bank | donate | While it is still safe to eat |
| F. Hold in the nearest cold room | hold | Stops the clock; costs today's delivery slot |

A–D are the options in the original brief. E and F split donating and holding
out of D, so that the four verbs a dispatcher actually presses — **sell, donate,
hold, reroute** — are each one button.

Assume the cargo stays at its current temperature until it reaches cooling. An option is feasible if freshness on arrival ≥ the store minimum.
`score = kg_saved × value_per_kg − extra_km × cost_per_km − markdown_loss` (constants in config). Pick the highest score and keep all options for display.

Two guards on the arithmetic:

- A shipment that will be accepted anyway is never moved: another option must
  beat A by `REROUTE_MIN_GAIN_QAR`.
- Selling and donating rescue food that is below the store's bar, because those
  channels have no bar. **Holding does not** — it only delays the loss — so once
  a load is out of specification, hold is credited with no kilos.

**The planner escalates instead of recommending** when the sensor cannot be
trusted, when no option meets the store minimum, when two genuinely different
verbs are within `REVIEW_MARGIN_QAR`, or when the best action is irreversible
and worth more than `REVIEW_VALUE_QAR`. It then sets `needs_human_review` with
written reasons, the agent says so instead of recommending, and the dashboard
shows the four verbs and waits. See `docs/decision-policy.md`.

### 7.5 Agent (LLM explanation only)

- Input: JSON of the chosen option, the alternatives and the facts (truck, product, temperatures, freshness numbers).
- Model: `qwen2.5:7b` via Ollama HTTP API at `localhost:11434`.
- Output: two sentences in Arabic and two in English, using only numbers from the JSON.
- Timeout 5 s → fall back to a fixed template with the same numbers.
- **Numeric guard:** the generated text is re-read and every standalone number in
  it (Arabic-Indic digits included) must appear in the facts, or the answer is
  thrown away and the template is used. Numbers inside names — `CO2e`, `qwen2.5`,
  `R1` — are not treated as figures.
- When `needs_human_review` is set, the model is told not to recommend anything.

### 7.6 Audit log

Every decision is saved with its evidence, and each record stores the hash of the previous record (tamper-evident chain).

## 8. The demo (about 4 minutes)

Scenario: **TRK-07** carries 2 t of lettuce on route R1 (Hamad Port → Industrial Area warehouse). It starts with 8 days of freshness, 1 day of trip left, and the store needs 6 days on arrival.

| Time | On stage | What judges see |
| --- | --- | --- |
| 0:00 | Box closed, fleet running | 12 trucks live on the map; TRK-07 labelled "LIVE sensor"; heat-risk layer |
| 0:40 | Lift the lid for 5 s | Bump and recovery; "door opening — no action" |
| 1:10 | Take out the sensor and hold it in a hand | Passes 8 °C and stays; alert after 30–45 s; freshness on arrival drops below 6 days (amber) |
| 2:00 | — | Options A–D with numbers; recommendation in Arabic and English |
| 2:45 | Tap Approve | Route redraws straight to the nearest store; freshness on arrival back above 6 days; audit entry |
| 3:20 | Comparison screen | Without ColdGuard: rejected. With ColdGuard: accepted, 2 t saved |
| 3:45 | Sensor back in the box | Temperature falls; judges can scan the QR code on the box |

Fallbacks: hardware backup switch (simulator takes over TRK-07), LLM template fallback, reset button, backup video.

## 9. Data pack (already built)

- `data/products.csv` — product rules (section 7.1).
- `data/places.csv` — port, border crossing, cold warehouse, cold store, supermarkets, food bank. **Approximate area-level coordinates** until the fetch runs.
- `data/routes.geojson` — routes R1–R6 with `distance_km`, `duration_min`, `source`.
  R1 Hamad Port → Industrial Area warehouse (TRK-07) · R2 warehouse → Al Wakrah · R3 warehouse → Lusail · R4 Abu Samra border → warehouse · R5 warehouse → Al Khor · R6 warehouse → Al Rayyan.
- `data/heat_by_hour.csv` — outside air temperature, humidity and a 0–100 heat-risk score per route per hour (synthetic September curve until the fetch runs).
- `data/dispatch_suggestions.csv` — best and worst departure (05:00–20:00) per route and freshness saved at loading.
- `scripts/build_data.py` — run `python scripts/build_data.py` with internet to replace approximations with OSRM roads, OpenStreetMap supermarkets and the Open-Meteo forecast. `--offline` keeps approximations. Every file has a `source` field.
- `scripts/places.py` — `PLACES`, `ROUTES`, `FLEET` (TRK-01…TRK-12; TRK-07 = real sensor).
- `simulator/sim.py` — `python simulator/sim.py --broker localhost` (or `--dry-run --ticks 3`). Seed 7 by default. Tested behaviour: door opening bumps about 6 °C then recovers; compressor failure reaches about 8 °C after 10 s and 16 °C after 30 s; restoring cooling returns to the setpoint in about 90 s.

## 10. Beyond the demo (platform features, for the pitch)

Built small for the demo: **heat-aware dispatch** ("leave at 05:00, not 14:00"), **surplus rescue** (option D notifies a food-bank account), **QR freshness passport** (scan the box → TRK-07 history).
Roadmap only (mock screens): phone-camera quality check at arrival, predictive maintenance of cooling units, multilingual driver voice alerts (Arabic, English, Urdu, Hindi, Malayalam), "ask the fleet" chat, sell-first (FEFO) warehouse lists, smart markdowns, national food-loss and CO₂ dashboard, cold-chain gap map, GS1 EPCIS digital passport.

## 11. Work breakdown

**Hardware / Arduino** — *needs the physical board; the sketch is written*
- [ ] Install IDE, board package and libraries; wire the DHT11; see readings in the Serial Monitor
- [x] Firmware publishes to MQTT with Wi-Fi and MQTT reconnect, an LED that is on
      while disconnected, `-127` on a failed read, optional lid switch — `firmware/node/node.ino`
- [ ] Build the cooler box; record resting temperature; record test traces (lid, hand, unplugged)
- [ ] Print the QR code for the box — `make qr`

**Backend**
- [x] docker-compose, schema, seed from `data/` (degrades to memory if Postgres is down)
- [x] Ingest (subscribe `coldguard/+/telemetry`; enrich TRK-07 with route position)
- [x] In-memory fleet state, REST endpoints, WebSocket
- [x] Approve → execute → audit; demo endpoints (fault, backup, reset); `/track/TRK-07`

**AI / logic**
- [x] `freshness.py`, `detector.py`, `planner.py`, `agent.py` per section 7
- [x] Unit tests on recorded traces and simulator faults — 72 tests, `make test`
- [x] Escalation to a human when the system should not decide (`docs/decision-policy.md`)

**Data / GIS**
- [ ] Run `build_data.py` with internet the day before; check routes and stores
- [x] Heat-risk map layer from `heat_by_hour.csv`; dispatch suggestion card

**Frontend**
- [x] Map with 12 trucks coloured by risk; TRK-07 "LIVE sensor"
- [x] Fleet list; TRK-07 panel with live chart (air and cargo) and freshness countdown; both clocks shown
- [x] Event log; alert card with options A–F, AR/EN text, Approve/Change; route redraw
- [x] Comparison screen; QR track page; hidden demo panel (press D); Arabic RTL toggle

**Pitch**
- [x] Deck outline and demo script — `pitch/DECK.md`, `pitch/DEMO_SCRIPT.md`
- [ ] Build the actual slides; 3 rehearsals; backup video

**Still open before the event**
- [ ] Flash the board and record the real resting temperature of the box
- [ ] `make model` on the demo laptop (qwen2.5:7b is about 5 GB)
- [ ] `make data` with internet, the day before
- [ ] Calibrate the product table against something better than assumptions

## 12. Build checkpoints

| Hour | Must be true |
| --- | --- |
| 1 | Contracts agreed; `docker compose up` works for everyone |
| 6 | NodeMCU readings visible with `mosquitto_sub -t 'coldguard/#'`; simulator publishing |
| 12 | Readings stored; freshness per truck; `GET /api/fleet` returns 12 trucks |
| 20 | Dashboard map live with freshness bars and heat layer |
| 26 | Real sensor: lid ignored, hand-warming triggers an alert on the dashboard |
| 34 | Options + AI explanation; Approve reroutes TRK-07 and writes the audit log |
| 40 | Backup switch, LLM fallback and reset all work |
| 44 | Feature freeze; 3 rehearsals; backup video |

## 13. Real vs simulated (say this in the pitch)

Real: TRK-07 temperature and humidity (NodeMCU + DHT11), the physical door-opening and warming events, the detector/freshness/planner code, the local AI explanation, the open heat and road data (after the fetch).
Simulated: the other 11 trucks, truck movement (on real roads), store stock, and executing actions (no real truck moves). Product parameters are literature-based assumptions.

Time is accelerated at two rates, both shown on screen: shelf life at ×120 and
map movement at ×10 (section 7.3). Say this plainly — a judge who spots it
before you do will assume the rest is also unsaid.

The cargo temperature is modelled, not measured: it is a lag on the air reading,
not a second sensor. A pulp probe would measure it directly, and that is the
first thing to add in a pilot.

## 14. Notes for Claude Code

- Start with the backend skeleton + ingest + `freshness.py`/`detector.py`, tested against `simulator/sim.py --dry-run` output, before the frontend.
- Keep configuration (DEMO_SPEED, thresholds, costs, broker host) in one `config.py` / `.env`.
- Never hard-code secrets; Wi-Fi credentials stay in the firmware only.
- Prefer small, readable modules; add a `make demo` or single script that starts everything and a `make reset`.
- If you change a data contract, update sections 6 and 9 of this file.
