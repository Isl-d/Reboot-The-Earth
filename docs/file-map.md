# Every file, by category

All 79 tracked files in the repository, grouped so that files doing the same
kind of job sit together. Every file appears exactly once, and the line counts
add up to the repository total, so this table is a complete inventory rather
than a summary.

| # | Category | Files | Lines |
| --- | --- | ---: | ---: |
| 1 | [Frontend — components](#1-frontend--components) | 10 | 751 |
| 2 | [Backend — decision logic](#2-backend--decision-logic) | 5 | 865 |
| 3 | [Backend — plumbing](#3-backend--plumbing) | 10 | 1493 |
| 4 | [Frontend — app shell and shared modules](#4-frontend--app-shell-and-shared-modules) | 9 | 829 |
| 5 | [Tests](#5-tests) | 8 | 919 |
| 6 | [Test fixtures — recorded traces](#6-test-fixtures--recorded-traces) | 5 | 1259 |
| 7 | [Data pack — static open data](#7-data-pack--static-open-data) | 5 | 311 |
| 8 | [Tooling — data, simulation, dev harness](#8-tooling--data-simulation-dev-harness) | 5 | 616 |
| 9 | [Firmware — the one real truck](#9-firmware--the-one-real-truck) | 2 | 199 |
| 10 | [Build, run and configuration](#10-build-run-and-configuration) | 8 | 203 |
| 11 | [Frontend — build configuration](#11-frontend--build-configuration) | 6 | 2243 |
| 12 | [Prose — brief, docs, pitch](#12-prose--brief-docs-pitch) | 6 | 923 |
| | **Total** | **79** | **10,611** |

This map itself is the eightieth file, in category 12.

Two rules decide which category a file lands in: **what it does at run time**
(decide, serve, display, measure) and **who owns it** (the lanes in
`README.md`). A file that only supports another file — a fixture, a lockfile, a
type declaration — sits next to the thing it supports.

---

## 1. Frontend — components

`web/src/components/` — one screen element each, all presentational, all fed
from `useLive`. None of them computes a number; they format what the backend
sent.

| File | Lines | What it shows |
| --- | ---: | --- |
| `Map.tsx` | 200 | Qatar basemap, OSRM routes, OSM places, 12 trucks coloured by risk, heat-risk layer |
| `AlertCard.tsx` | 104 | The at-risk shipment: recommendation, or the four verbs when the planner escalated |
| `TruckPanel.tsx` | 91 | One shipment in detail — live chart, freshness countdown, arrival verdict |
| `DemoPanel.tsx` | 88 | Hidden presenter controls (press `D`): faults, backup switch, reset |
| `OptionsTable.tsx` | 61 | Options A–F with every number, so a judge can check the recommendation |
| `FleetList.tsx` | 52 | Twelve trucks, worst first, TRK-07 marked as the real sensor |
| `EventLog.tsx` | 43 | Door openings, defrosts, sensor faults, failures — newest first |
| `ComparisonScreen.tsx` | 41 | The closing slide: the same shipment with and without ColdGuard |
| `Sparkline.tsx` | 37 | Air reading vs. modelled cargo temperature, the two-line chart |
| `DispatchCard.tsx` | 34 | Heat-aware dispatch — best and worst departure time per route |

## 2. Backend — decision logic

The deterministic core. Every number the demo shows is produced here, and
nothing in this group talks to MQTT, the database or the network — which is why
these are the files the tests hit hardest.

| File | Lines | Responsibility |
| --- | ---: | --- |
| `backend/planner.py` | 307 | Options A–F, money-and-kilometres scoring, escalation to a human (§7.4) |
| `backend/detector.py` | 198 | Door vs. defrost vs. sensor fault vs. cooling failure (§7.2) |
| `backend/agent.py` | 163 | Qwen2.5 explanation, numeric guard, template fallback (§7.5) |
| `backend/freshness.py` | 127 | Q10 shelf-life model, freshness on arrival, risk (§7.3) |
| `backend/audit.py` | 70 | Hash-chained decision log and `verify()` (§7.6) |

## 3. Backend — plumbing

Everything that moves data in, holds it, and serves it out. The split from
group 2 is deliberate: these files have I/O and shared mutable state, those
files are pure arithmetic.

| File | Lines | Responsibility |
| --- | ---: | --- |
| `backend/main.py` | 338 | FastAPI app — REST, WebSocket, `/track/TRK-07`, demo endpoints |
| `backend/state.py` | 329 | In-memory fleet, product-temperature lag, risk projection, reroutes |
| `backend/ingest.py` | 208 | MQTT subscriber → validate → enrich → detector → freshness → planner |
| `backend/db.py` | 167 | PostgreSQL writes, seeding from `data/*.csv`, degrades to memory only |
| `backend/geo.py` | 148 | Places, routes, haversine distance along the polyline |
| `backend/config.py` | 105 | Every threshold, cost and clock, overridable with `COLDGUARD_*` |
| `backend/__init__.py` | 1 | Package marker |

Schema and the server-rendered QR page live with the backend but are not Python
— see groups 10 and 4 respectively for their neighbours in kind:

| File | Lines | What it is |
| --- | ---: | --- |
| `backend/schema.sql` | 76 | Six tables, TimescaleDB optional |
| `backend/seed.sql` | 8 | Truncates the tables `db.py` rebuilds from CSV on every start |
| `backend/templates/track.html` | 113 | The phone page behind the QR code on the cooler box |

## 4. Frontend — app shell and shared modules

`web/src/` — the files every component depends on. One each for layout, live
data, the API contract, language, colour and type.

| File | Lines | Responsibility |
| --- | ---: | --- |
| `i18n.ts` | 188 | English and Arabic chrome (decision text arrives already bilingual) |
| `index.css` | 183 | The whole stylesheet, including RTL |
| `types.ts` | 159 | Mirrors the backend JSON — keep in step with CLAUDE.md §6 |
| `App.tsx` | 106 | Layout, language toggle, which panel is open |
| `useLive.ts` | 104 | One WebSocket, one copy of the fleet, read by everything on screen |
| `api.ts` | 48 | Every REST call the dashboard makes, in one place |
| `theme.ts` | 30 | Risk colours and number formatting, shared by map, list and charts |
| `main.tsx` | 10 | React entry point |
| `vite-env.d.ts` | 1 | Vite client type reference |

## 5. Tests

One test file per module under test, plus the end-to-end run. 72 tests, about
half a second, no broker and no database.

| File | Lines | Covers |
| --- | ---: | --- |
| `tests/test_api.py` | 199 | The whole four-minute demo in-process: telemetry → alert → approve |
| `tests/test_planner.py` | 175 | Options and scoring (§7.4) |
| `tests/test_state.py` | 152 | Cargo-temperature lag, risk projection, reroutes |
| `tests/test_detector.py` | 140 | Detector rules, replayed against the recorded traces |
| `tests/test_agent.py` | 128 | The agent writes words, never numbers |
| `tests/test_freshness.py` | 66 | The Q10 model (§7.3) |
| `tests/test_audit.py` | 53 | The hash chain, including a deliberately tampered record |
| `tests/conftest.py` | 6 | Puts the repository root on `sys.path` |

## 6. Test fixtures — recorded traces

Simulator output at seed 7, frozen to JSON so the detector tests never need
MQTT and always see the exact behaviour the judges will.

| File | Lines | Scenario |
| --- | ---: | --- |
| `tests/traces/compressor.json` | 601 | Cooling failure: ~8 °C at 10 s, ~16 °C at 30 s, recovery in ~90 s |
| `tests/traces/door.json` | 301 | Lid open: ~6 °C bump, then recovery — the "no action" case |
| `tests/traces/sensor.json` | 151 | A sensor reporting −127 |
| `tests/traces/steady.json` | 151 | A healthy truck, the negative control |
| `tests/traces/make_traces.py` | 55 | Regenerates all four from `simulator/sim.py` |

## 7. Data pack — static open data

Reference data, loaded by `backend/db.py` and `backend/geo.py`. Every file
carries a `source` column or property saying whether a number is real open data
or an approximation.

| File | Rows | Contents |
| --- | ---: | --- |
| `data/heat_by_hour.csv` | 288 | Outside temperature, humidity and a 0–100 heat score per route per hour |
| `data/places.csv` | 10 | Port, border crossing, warehouse, cold store, supermarkets, food bank |
| `data/routes.geojson` | 6 | Routes R1–R6 with geometry, `distance_km`, `duration_min` |
| `data/dispatch_suggestions.csv` | 6 | Best and worst departure per route, freshness saved at loading |
| `data/products.csv` | 3 | Lettuce, chicken, milk: ideal °C, life, Q10, alert limit, value |

## 8. Tooling — data, simulation, dev harness

Scripts a person runs by hand, never part of the serving process.

| File | Lines | What it does |
| --- | ---: | --- |
| `simulator/sim.py` | 208 | Eleven virtual trucks plus TRK-07 backup mode, with triggerable faults |
| `scripts/build_data.py` | 201 | Fetches OSRM roads, OSM supermarkets, Open-Meteo forecast (`--offline` keeps approximations) |
| `scripts/dev_no_broker.py` | 101 | The whole demo on one laptop with no broker, database or Docker |
| `scripts/make_qr.py` | 58 | The QR code for the cooler-box lid |
| `scripts/places.py` | 48 | `PLACES`, `ROUTES`, `FLEET` — shared by the simulator and the data build |

## 9. Firmware — the one real truck

| File | Lines | What it is |
| --- | ---: | --- |
| `firmware/node/node.ino` | 142 | NodeMCU ESP8266 + DHT11: publishes to `coldguard/TRK-07/telemetry` every 2 s, with Wi-Fi/MQTT reconnect, status LED, `-127` on a failed read, optional lid switch |
| `firmware/node/README.md` | 57 | Wiring, board package, libraries, building the cooler box |

The only file in the repository that holds credentials, and they stay there:
Wi-Fi SSID and password are edited into `node.ino` and never committed real.

## 10. Build, run and configuration

One command per thing you do on stage; one place for every tunable number.

| File | Lines | What it is |
| --- | ---: | --- |
| `docker-compose.yml` | 80 | mosquitto · db · backend · simulator · ollama · web |
| `Makefile` | 47 | `make demo`, `make test`, `make data`, `make model`, `make qr`, `make reset` |
| `.env.example` | 23 | Every `COLDGUARD_*` override, with the warning about Wi-Fi credentials |
| `backend/Dockerfile` | 15 | Python 3.11-slim, `requirements.txt`, uvicorn |
| `.gitignore` | 14 | `__pycache__`, `.venv`, `node_modules`, `.env` |
| `requirements.txt` | 10 | FastAPI, uvicorn, paho-mqtt ≥ 2.0, psycopg, and the data-lane deps |
| `web/Dockerfile` | 8 | Node 20-alpine, `npm install`, Vite dev server |
| `mosquitto/mosquitto.conf` | 6 | Anonymous listener on 1883 — demo laptop only |

## 11. Frontend — build configuration

| File | Lines | What it is |
| --- | ---: | --- |
| `web/package-lock.json` | 2170 | Pinned dependency tree (generated) |
| `web/package.json` | 23 | React, Vite, TypeScript, MapLibre GL |
| `web/tsconfig.json` | 19 | ES2022, strict |
| `web/vite.config.ts` | 17 | Dev proxy to the backend on :8000 |
| `web/index.html` | 12 | The single page |
| `web/.dockerignore` | 2 | `node_modules`, `dist` |

## 12. Prose — brief, docs, pitch

| File | Lines | Audience |
| --- | ---: | --- |
| `CLAUDE.md` | 415 | The brief and the single source of truth for every contract |
| `README.md` | 163 | Anyone who clones the repository |
| `docs/decision-policy.md` | 132 | When ColdGuard decides and when it asks a human |
| `docs/data-pack.md` | 73 | What is in `data/`, how to refresh it, how to drive the simulator |
| `pitch/DECK.md` | 72 | Twelve slides, one number per slide |
| `pitch/DEMO_SCRIPT.md` | 68 | The four-minute run, minute by minute, with fallbacks |
| `docs/file-map.md` | — | This file |

---

## Where a new file goes

| If it… | Put it in | Category |
| --- | --- | --- |
| computes a number from telemetry | `backend/` | 2 |
| moves, stores or serves data | `backend/` | 3 |
| draws one thing on screen | `web/src/components/` | 1 |
| is shared by several components | `web/src/` | 4 |
| is run by a person, not by the server | `scripts/` | 8 |
| is reference data | `data/`, with a `source` column | 7 |
| pins behaviour the demo depends on | `tests/` | 5 |

Two invariants this map exists to protect: the LLM never produces numbers
(group 2 has no network calls in the direction of the model except `agent.py`,
which guards every digit), and a contract change touches `CLAUDE.md` §6,
`backend/schema.sql` and `web/src/types.ts` in the same commit.
