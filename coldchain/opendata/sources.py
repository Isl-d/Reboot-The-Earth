"""Catalogue of open data for cold-chain logistics.

Every source a refrigerated fleet needs, with its licence and how to get it.
Nothing proprietary is listed: if a source cannot be redistributed under an
open licence it does not belong here, and a few well-known ones are named in
EXCLUDED below precisely so nobody reaches for them by mistake.

Two access classes:

* `offline`  — already on this machine, shipped inside an open-source Python
               package. Works with no network at all.
* `network`  — a free public endpoint, no account and no API key, fetched by
               coldchain/opendata/network.py when egress is allowed.

`fetched` is never assumed. `provenance.json` records what actually arrived,
when, and from where, so a number on the dashboard can always be traced back.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Access = Literal["offline", "network"]


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    category: str
    provides: str            # what a refrigerated fleet actually uses it for
    licence: str
    url: str
    access: Access
    output: str = ""         # the file it lands in, under coldchain/data/
    notes: str = ""
    needs: tuple[str, ...] = field(default_factory=tuple)


SOURCES: tuple[Source, ...] = (
    # ------------------------------------------------------- geography
    Source(
        key="geonames_places",
        name="GeoNames populated places",
        category="geography",
        provides="Real coordinates for every town the fleet serves, so routes "
                 "and depots are not invented.",
        licence="CC BY 4.0",
        url="https://www.geonames.org/",
        access="offline",
        output="open_places.csv",
        notes="Ships inside the geonamescache package (MIT), so it works with "
              "no network.",
        needs=("geonamescache",),
    ),
    Source(
        key="osm_cold_sites",
        name="OpenStreetMap cold-chain sites (Overpass)",
        category="geography",
        provides="Ports, warehouses, cold stores, supermarkets, food banks "
                 "and fuel stations — the places a reefer actually stops.",
        licence="ODbL 1.0",
        url="https://overpass-api.de/api/interpreter",
        access="network",
        output="osm_sites.csv",
        notes="Attribution required: © OpenStreetMap contributors.",
    ),
    Source(
        key="osm_hgv_restrictions",
        name="OpenStreetMap HGV restrictions",
        category="geography",
        provides="Weight, height and access limits on roads — a 2 t reefer "
                 "cannot take every shortcut a car can.",
        licence="ODbL 1.0",
        url="https://overpass-api.de/api/interpreter",
        access="network",
        output="osm_hgv_restrictions.csv",
    ),
    Source(
        key="osrm_routes",
        name="OSRM road routing",
        category="routing",
        provides="Real road geometry, distance and duration between depots "
                 "and stores, instead of straight lines.",
        licence="Software BSD-2-Clause; road data ODbL (OpenStreetMap)",
        url="https://router.project-osrm.org/",
        access="network",
        output="open_routes.geojson",
        notes="The demo server is rate limited and is not for production "
              "load; self-host OSRM for anything beyond a demo.",
    ),
    Source(
        key="natural_earth",
        name="Natural Earth coastlines and boundaries",
        category="geography",
        provides="A basemap that works offline, so the map still draws with "
                 "no tile server.",
        licence="Public domain",
        url="https://www.naturalearthdata.com/",
        access="network",
        output="natural_earth_qatar.geojson",
    ),

    # --------------------------------------------------------- weather
    Source(
        key="open_meteo_forecast",
        name="Open-Meteo forecast",
        category="weather",
        provides="Ambient temperature, humidity and solar radiation along "
                 "each route — the heat load a reefer has to fight.",
        licence="CC BY 4.0",
        url="https://api.open-meteo.com/v1/forecast",
        access="network",
        output="open_weather_forecast.csv",
        notes="No account and no API key.",
    ),
    Source(
        key="open_meteo_archive",
        name="Open-Meteo historical (ERA5)",
        category="weather",
        provides="Years of past ambient temperature, to calibrate the heat "
                 "model against a real Gulf summer rather than a guess.",
        licence="CC BY 4.0 (ERA5 via Copernicus)",
        url="https://archive-api.open-meteo.com/v1/archive",
        access="network",
        output="open_weather_history.csv",
    ),
    Source(
        key="nasa_power",
        name="NASA POWER",
        category="weather",
        provides="Solar irradiance and surface temperature, an independent "
                 "cross-check on the weather feed.",
        licence="Public domain (US Government)",
        url="https://power.larc.nasa.gov/api/temporal/daily/point",
        access="network",
        output="nasa_power_daily.csv",
    ),

    # ---------------------------------------------------- food science
    Source(
        key="product_reference",
        name="Product storage reference (shipped table)",
        category="food-science",
        provides="Safe temperature band, ideal humidity, shelf life and Q10 "
                 "per commodity — what every freshness number is computed from.",
        licence="Values are facts from the cited open sources; this table is "
                "our transcription of them",
        url="https://www.ars.usda.gov/arsuserfiles/oc/np/commercialstorage/commercialstorage.pdf",
        access="offline",
        output="product_reference.csv",
        notes="EVERY ROW IS MARKED verified=no. These are literature-recalled "
              "values, not values this machine downloaded. They are here so "
              "the platform runs offline, and each carries the citation to "
              "check it against. Do not present one to a judge as sourced.",
    ),
    Source(
        key="usda_handbook_66",
        name="USDA Agriculture Handbook 66",
        category="food-science",
        provides="The authoritative storage conditions for fresh produce, to "
                 "replace the transcribed table with extracted values.",
        licence="Public domain (US Government)",
        url="https://www.ars.usda.gov/arsuserfiles/oc/np/commercialstorage/commercialstorage.pdf",
        access="network",
        output="usda_handbook_66.csv",
        notes="A 700-page PDF, so it needs table extraction rather than a "
              "plain download. No fetcher written yet - see SOURCES.md.",
    ),
    Source(
        key="codex_alimentarius",
        name="Codex Alimentarius cold-chain codes",
        category="food-science",
        provides="The internationally agreed temperature limits a shipment "
                 "is judged against at the gate.",
        licence="Open (FAO/WHO)",
        url="https://www.fao.org/fao-who-codexalimentarius/codex-texts/codes-of-practice/en/",
        access="network",
        output="codex_limits.csv",
    ),
    Source(
        key="unece_atp",
        name="UNECE ATP agreement",
        category="food-science",
        provides="Classes for refrigerated vehicles and the temperatures "
                 "each class must hold — what a truck is certified to do.",
        licence="Open (United Nations)",
        url="https://unece.org/transport/standards/transport/perishable-foodstuffs",
        access="network",
        output="atp_vehicle_classes.csv",
    ),
    Source(
        key="fao_food_loss",
        name="FAO Food Loss and Waste database",
        category="impact",
        provides="Observed loss percentages by commodity and stage — the "
                 "baseline the 'without ColdGuard' number is measured against.",
        licence="CC BY-NC-SA 3.0 IGO",
        url="https://www.fao.org/platform-food-loss-waste/flw-data/en/",
        access="network",
        output="fao_food_loss.csv",
        notes="NonCommercial: fine for a hackathon and for research, but it "
              "cannot be shipped in a commercial product. Flagged in "
              "SOURCES.md for that reason.",
    ),

    # --------------------------------------------------------- vehicle
    Source(
        key="defra_ghg_factors",
        name="UK DESNZ/DEFRA greenhouse gas conversion factors",
        category="emissions",
        provides="kg CO2e per tonne-kilometre for refrigerated HGVs, and "
                 "refrigerant leakage factors — how the CO2e saved is worked out.",
        licence="Open Government Licence v3.0",
        url="https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting",
        access="network",
        output="emission_factors.csv",
    ),
    Source(
        key="eea_emep_transport",
        name="EEA/EMEP road transport emission inventory",
        category="emissions",
        provides="Fuel burn and emissions per vehicle class, for the diesel "
                 "a longer reroute actually costs.",
        licence="CC BY 4.0 (European Environment Agency)",
        url="https://www.eea.europa.eu/publications/emep-eea-guidebook-2023",
        access="network",
        output="eea_transport_factors.csv",
    ),

    # --------------------------------------------------------- physics
    Source(
        key="psychrometrics",
        name="Psychrometric relations (Magnus/Tetens)",
        category="physics",
        provides="Dew point from temperature and humidity: whether opening a "
                 "door in Gulf humidity will condense water onto the product.",
        licence="Public domain (published formulae)",
        url="https://doi.org/10.1175/BAMS-86-2-225",
        access="offline",
        output="psychrometrics.csv",
        notes="Computed here from the published coefficients rather than "
              "downloaded, so it works with no network.",
    ),

    # ----------------------------------------------------- operational
    Source(
        key="public_holidays",
        name="Public holidays",
        category="operational",
        provides="Days a store will not accept a delivery — a shipment that "
                 "arrives fresh on a closed dock is still a loss.",
        licence="MIT (package); underlying holiday dates are facts",
        url="https://github.com/vacanza/holidays",
        access="offline",
        output="public_holidays.csv",
        needs=("holidays",),
    ),
)

# Named so nobody reaches for them: each is useful but not openly licensed.
EXCLUDED: tuple[tuple[str, str], ...] = (
    ("GLEC Framework", "Freely readable but not an open licence; no redistribution."),
    ("GADM administrative boundaries", "Non-commercial only, and no redistribution."),
    ("Google Maps / Places", "Proprietary, paid, and the terms forbid caching."),
    ("ASHRAE Handbook (Refrigeration)", "Copyright ASHRAE; the formulae are "
                                        "public, the tables are not."),
    ("Commercial reefer telematics feeds", "Proprietary and per-fleet."),
)


def by_access(access: Access) -> tuple[Source, ...]:
    return tuple(s for s in SOURCES if s.access == access)


def by_key(key: str) -> Source | None:
    return next((s for s in SOURCES if s.key == key), None)


def categories() -> tuple[str, ...]:
    return tuple(dict.fromkeys(s.category for s in SOURCES))
