# ColdGuard

**A live freshness score for every pallet of food.**
UN *Reboot the Earth* hackathon, Carnegie Mellon University in Qatar — Challenge 2,
*AI for Cold-Chain Monitoring and Food-Loss Reduction*.

Sensors report temperature. ColdGuard tells a real refrigeration failure apart
from a door opening, works out how many days of freshness are left and whether
the food will still be accepted when it arrives, and recommends what to do —
**reroute, sell, donate or hold** — which a person approves with one tap.

One truck in the demo is real: **TRK-07** is a NodeMCU and a DHT11 taped inside
a cooler box. The other eleven are simulated on real Qatari roads.

```
NodeMCU (TRK-07) ─┐
                  ├─ MQTT ─→ FastAPI backend ─→ PostgreSQL
Simulator (11) ───┘            │  ingest · detector · freshness · planner · agent · audit
                               ├─→ Ollama (Qwen2.5-7B, on this laptop) for the words
                               └─→ REST + WebSocket ─→ dashboard (React + MapLibre)
```

## Start here

Everything is open source and runs on one laptop with no internet, no cloud and
no API keys.

```bash
make demo          # docker compose up: broker, database, backend, simulator, dashboard
```

Then open **http://localhost:5173**. Press **D** for the demo panel.

No Docker? Nothing to install but Python and Node:

```bash
pip install -r requirements.txt
python scripts/dev_no_broker.py --script     # backend on :8000, fleet running, demo acting itself out
cd web && npm install && npm run dev         # dashboard on :5173
```

`--script` replays what the presenter does to the physical box, so you can build
against the real sequence of events without the hardware.

| Thing | Where |
| --- | --- |
| Dashboard | http://localhost:5173 |
| API | http://localhost:8000/api/fleet |
| Freshness passport (the QR code on the box) | http://localhost:8000/track/TRK-07 |
| Raw telemetry | `make watch` |

Before the event, once: `make model` pulls `qwen2.5:7b` (about 5 GB), and
`make data` refetches the open data so the heat forecast covers demo day.

## How it works

Four modules, all deterministic Python. **The LLM never produces a number.**

**`backend/detector.py`** — separates four things from one temperature stream:
a *door opening* (a rise that comes back on its own), a *defrost cycle* (a small
bump), a *sensor fault* (−127, a silent board, an impossible jump) and a
*cooling failure* (above the product's limit, door closed, not falling). Only
the last one raises an alert. Lifting the lid on stage is deliberately boring.

**`backend/freshness.py`** — the Q10 rule: ten degrees warmer means food ages
Q10 times faster. Two refinements that matter:

- The clock runs on the **cargo temperature**, not the air reading. A DHT11
  spikes in seconds; two tonnes of lettuce follow with a lag of about two hours.
  The dashboard charts both lines, and the gap between them is the honest part.
- Risk assumes a warm spell is fixed within the hour — unless the detector has
  *confirmed* a cooling failure, and then the projection is the worst case: it
  stays broken all the way. A lifted lid never turns the fleet amber.

**`backend/planner.py`** — six options, each with its kilometres and its money:

| | Action | |
| --- | --- | --- |
| A | continue | Continue as planned |
| B | reroute | Divert to the nearest cold store, then continue |
| C | reroute | Deliver direct to the nearest supermarket, skipping the hub |
| D | sell | Sell today at a markdown |
| E | donate | Donate to the food bank while it is still safe to eat |
| F | hold | Park in the nearest cold room and decide later |

`score = kg_saved × value_per_kg − extra_km × cost_per_km − markdown_loss`.
A healthy shipment is never moved. Holding earns nothing once a load is already
out of specification, because holding only delays the loss.

**The planner also refuses to decide** when the arithmetic should not settle it:
the sensor cannot be trusted, nothing meets the store's minimum, two genuinely
different actions are worth the same, or the best action is irreversible and
large. The dashboard then shows **Sell / Donate / Hold / Reroute** with no
recommendation and waits for a person. See
[docs/decision-policy.md](docs/decision-policy.md).

**`backend/agent.py`** — `qwen2.5:7b` on `localhost:11434` turns a JSON of facts
into two sentences of English and two of Arabic. Three things keep it honest:
the prompt forbids arithmetic, a guard re-reads the output and rejects any
number that is not in the facts (Arabic-Indic digits included), and a fixed
template writes the same sentences if the model is slow, missing or ungrounded.
**The demo never depends on the LLM.**

**`backend/audit.py`** — every decision is stored with the evidence it was based
on, and each record carries the hash of the one before it. Edit history and
`verify()` names the record where the chain breaks.

## Two clocks, both on screen

| Clock | Rate | What it drives |
| --- | --- | --- |
| Shelf life | ×120 | 1 second on stage = 2 minutes of spoilage |
| Map | ×10 | A truck crosses its route over the four minutes of the demo |

Without the second one, every truck would reach its destination twenty seconds
into the demo. Both are labelled in the interface.

## What is real and what is not

**Real:** TRK-07's temperature and humidity, the physical door opening and the
warming, all of the detector, freshness, planner and audit code, the local AI
explanation, and the open road, place and weather data after `make data`.

**Simulated:** the other eleven trucks, the movement along the roads, store
stock, and carrying the actions out — no real truck moves. Time is accelerated
and shown on screen. The product parameters are literature-based assumptions,
and every data file carries a `source` column saying so.

## Repository

```
backend/     FastAPI: ingest · detector · freshness · planner · agent · audit · main
web/         React + Vite + TypeScript + MapLibre dashboard
firmware/    NodeMCU sketch and the hardware notes
simulator/   eleven virtual trucks, with faults you can trigger
scripts/     open-data fetch, place and route definitions, QR code, dev harness
data/        products, places, routes, heat by hour, dispatch suggestions
tests/       72 tests, including the whole four-minute demo end to end
docs/        decision policy, data pack, contracts
pitch/       demo script and deck outline
```

`CLAUDE.md` is the project brief and the single source of truth for the
contracts. Change a contract there and here in the same commit.

```bash
make test        # 72 tests, about half a second
```

## Team

| Lane | Files |
| --- | --- |
| Hardware | `firmware/`, `scripts/make_qr.py` |
| Backend | `backend/main.py`, `ingest.py`, `db.py` |
| AI and logic | `backend/detector.py`, `freshness.py`, `planner.py`, `agent.py`, `tests/` |
| Data and GIS | `scripts/build_data.py`, `data/` |
| Frontend | `web/src/` |
| Pitch | `pitch/` |

Configuration lives in one place: `backend/config.py`, overridable with
`COLDGUARD_*` environment variables (see `.env.example`). Wi-Fi credentials live
in the firmware and nowhere else — never commit a real one.
