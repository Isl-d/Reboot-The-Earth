# Open data for cold-chain logistics

Every dataset this platform uses, what a refrigerated fleet needs it for, and
the licence it comes under. Nothing proprietary is here.

Regenerate with:

```bash
python -m coldchain.opendata.fetch            # everything reachable
python -m coldchain.opendata.fetch --offline  # no network attempts
python -m coldchain.opendata.fetch --list     # this catalogue, from the code
```

`provenance.json` is written on every run and records, per source, whether the
data actually arrived, when, how many rows, and under what licence. Check it
before quoting a number.

## Available with no network

These ship inside open-source packages or are computed from published
formulae, so they work on a laptop with nothing installed and on a stage with
no internet.

| Data | Rows | Licence | Used for |
| --- | ---: | --- | --- |
| `open_places.csv` — GeoNames populated places | 26 | CC BY 4.0 | Real coordinates for the towns the fleet serves |
| `public_holidays.csv` — Qatar 2026–27 | 16 | MIT (package); dates are facts | Days a store will not accept a delivery |
| `psychrometrics.csv` — dew point table | 144 | Public domain formulae | Whether opening a door will condense water onto the product |
| `product_reference.csv` — storage conditions | 7 | Transcribed from cited open sources | Safe band, shelf life and Q10 per commodity |

## Needs network access

Free public endpoints, no account and no API key. Run the fetcher the day
before the event.

| Source | Licence | Used for | Fetcher |
| --- | --- | --- | --- |
| OpenStreetMap via Overpass | ODbL 1.0 | Ports, warehouses, cold stores, supermarkets, food banks | written |
| OSM HGV restrictions | ODbL 1.0 | Weight and height limits a loaded reefer must respect | written |
| OSRM routing | BSD-2 software, ODbL data | Real road geometry, distance and duration | written |
| Open-Meteo forecast | CC BY 4.0 | Ambient temperature, humidity, solar — the heat load | written |
| Open-Meteo archive (ERA5) | CC BY 4.0 | A year of past ambient, to calibrate rather than guess | written |
| Natural Earth | Public domain | Offline basemap | not yet |
| NASA POWER | Public domain | Independent solar and temperature cross-check | not yet |
| USDA Agriculture Handbook 66 | Public domain | Authoritative produce storage conditions | not yet — 700-page PDF, needs table extraction |
| Codex Alimentarius | Open (FAO/WHO) | The temperature limits a shipment is judged against | not yet |
| UNECE ATP | Open (UN) | Refrigerated vehicle classes and what each must hold | not yet |
| FAO Food Loss and Waste | CC BY-NC-SA 3.0 IGO | Observed loss rates — the "without ColdGuard" baseline | not yet |
| UK DESNZ/DEFRA GHG factors | Open Government Licence v3.0 | kg CO2e per tonne-km for refrigerated HGVs | not yet |
| EEA/EMEP road transport | CC BY 4.0 | Fuel burn per vehicle class, cost of a longer reroute | not yet |

## Two things to be careful about

**`product_reference.csv` is unverified.** Every row carries `verified=no` and
a citation. They are literature-recalled values written down so the platform
runs offline — not values any machine here downloaded. They are in the right
region for each commodity, but do not present one to a judge as a sourced
figure until the USDA and Codex fetches have replaced it.

**FAO Food Loss and Waste is NonCommercial.** Fine for a hackathon and for
research, and it cannot ship in a commercial product. It is the only
non-commercial source in the list, and it is flagged here so nobody builds a
business case on it by accident.

## Attribution the demo owes

If the map draws OSM-derived geometry, the page must say **© OpenStreetMap
contributors**. Open-Meteo and GeoNames are CC BY and want attribution too.
One credit line covers all three:

> Map data © OpenStreetMap contributors (ODbL). Weather © Open-Meteo (CC BY
> 4.0). Places © GeoNames (CC BY 4.0).

## Deliberately excluded

Named so nobody reaches for them by mistake:

| Not used | Why |
| --- | --- |
| GLEC Framework | Freely readable, but not an open licence and no redistribution |
| GADM boundaries | Non-commercial only, and no redistribution |
| Google Maps / Places | Proprietary, paid, and the terms forbid caching |
| ASHRAE Handbook tables | The formulae are public; the tables are copyright |
| Commercial reefer telematics | Proprietary and per-fleet |
