"""Open data that needs no network at all.

Each of these ships inside an open-source package already on the machine, or
is computed from published formulae. They run on a laptop with no internet and
on a stage with no internet, which is the point.
"""
from __future__ import annotations

import csv
import logging
import math
from datetime import date
from pathlib import Path
from typing import Any

log = logging.getLogger("coldchain.opendata")

# Countries the demo fleet operates in. Widen this and everything below
# follows.
COUNTRIES = ("QA",)
HOLIDAY_YEARS = (2026, 2027)


def _write(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


# ------------------------------------------------------------------ places
def fetch_places(out: Path) -> dict[str, Any]:
    """Real populated places from GeoNames, via the geonamescache package."""
    try:
        import geonamescache
    except ImportError:
        return {"ok": False, "reason": "geonamescache is not installed"}

    gc = geonamescache.GeonamesCache()
    rows = []
    for city in gc.get_cities().values():
        if city["countrycode"] not in COUNTRIES:
            continue
        rows.append({
            "geonameId": city["geonameid"],
            "name": city["name"],
            "countryCode": city["countrycode"],
            "latitude": round(float(city["latitude"]), 6),
            "longitude": round(float(city["longitude"]), 6),
            "population": city["population"],
            "timezone": city.get("timezone", ""),
            "source": "GeoNames (CC BY 4.0) via geonamescache",
        })
    rows.sort(key=lambda r: -r["population"])
    n = _write(out, rows, ["geonameId", "name", "countryCode", "latitude",
                           "longitude", "population", "timezone", "source"])
    return {"ok": True, "rows": n}


# ---------------------------------------------------------------- holidays
def fetch_holidays(out: Path) -> dict[str, Any]:
    """Days a store will not take a delivery.

    A shipment that arrives perfectly chilled at a closed dock is still a
    loss, so the dispatch planner needs these as much as it needs the weather.
    """
    try:
        import holidays as holidays_pkg
    except ImportError:
        return {"ok": False, "reason": "holidays is not installed"}

    rows = []
    for country in COUNTRIES:
        try:
            cal = holidays_pkg.country_holidays(country, years=list(HOLIDAY_YEARS))
        except NotImplementedError:
            log.warning("no holiday calendar for %s", country)
            continue
        for day, name in sorted(cal.items()):
            rows.append({
                "countryCode": country,
                "date": day.isoformat(),
                "name": name,
                "weekday": day.strftime("%A"),
                "source": "python-holidays (MIT)",
            })
    n = _write(out, rows, ["countryCode", "date", "name", "weekday", "source"])
    return {"ok": True, "rows": n}


# --------------------------------------------------------- psychrometrics
# Magnus/Tetens coefficients over water, as given by Alduchov & Eskridge
# (1996) and reproduced in Lawrence (2005), BAMS 86(2), 225-233.
_A, _B = 17.625, 243.04


def dew_point_c(temp_c: float, rh_pct: float) -> float:
    """Dew point in Celsius for an air temperature and relative humidity."""
    rh = max(1e-6, min(100.0, rh_pct)) / 100.0
    gamma = math.log(rh) + (_A * temp_c) / (_B + temp_c)
    return (_B * gamma) / (_A - gamma)


def condensation_risk(product_c: float, air_c: float, rh_pct: float) -> bool:
    """True when the product is colder than the dew point of the air on it.

    This is the thing that ruins a carton in a Gulf summer: warm humid air
    meets a cold pallet at an open door and water condenses onto the product,
    which then supports mould long before the temperature alone would.
    """
    return product_c < dew_point_c(air_c, rh_pct)


def fetch_psychrometrics(out: Path) -> dict[str, Any]:
    """A lookup table of dew points across the conditions the fleet sees."""
    rows = []
    for air_c in range(20, 51, 2):            # a Gulf day, 20 to 50 C
        for rh in range(20, 101, 10):
            dp = dew_point_c(float(air_c), float(rh))
            rows.append({
                "airTempC": air_c,
                "relativeHumidityPct": rh,
                "dewPointC": round(dp, 2),
                # A chilled pallet sits near 2 C; below the dew point it wets.
                "condensesOn2CPallet": "yes" if 2.0 < dp else "no",
                "source": "Magnus/Tetens coefficients, Alduchov & Eskridge 1996",
            })
    n = _write(out, rows, ["airTempC", "relativeHumidityPct", "dewPointC",
                           "condensesOn2CPallet", "source"])
    return {"ok": True, "rows": n}


# ----------------------------------------------------- product reference
# Storage conditions for the demo commodities.
#
# HONESTY: these are literature-recalled values, not values this machine has
# downloaded. Every row is marked `verified=no` and carries the citation to
# check it against. `python -m coldchain.opendata.fetch` replaces them with
# extracted values once USDA Handbook 66 can be reached. Do not present an
# unverified row to a judge as a sourced figure.
PRODUCT_REFERENCE: tuple[dict[str, Any], ...] = (
    dict(productId="CHICKEN", name="Fresh chicken", safeMinTempC=-2, safeMaxTempC=4,
         idealTempC=0, recommendedRhPct=95, typicalShelfLifeDays=7, q10=3.0,
         citation="Codex CAC/RCP 58-2005; USDA FSIS poultry storage guidance"),
    dict(productId="FISH", name="Fresh fish", safeMinTempC=-1, safeMaxTempC=2,
         idealTempC=0, recommendedRhPct=95, typicalShelfLifeDays=3, q10=3.0,
         citation="Codex CAC/RCP 52-2003 (fish and fishery products)"),
    dict(productId="MILK", name="Fresh milk", safeMinTempC=1, safeMaxTempC=6,
         idealTempC=4, recommendedRhPct=85, typicalShelfLifeDays=10, q10=2.5,
         citation="Codex CAC/RCP 57-2004 (milk and milk products)"),
    dict(productId="LETTUCE", name="Lettuce", safeMinTempC=0, safeMaxTempC=8,
         idealTempC=0, recommendedRhPct=98, typicalShelfLifeDays=14, q10=3.0,
         citation="USDA Agriculture Handbook 66, leafy vegetables"),
    dict(productId="TOMATO", name="Tomato", safeMinTempC=10, safeMaxTempC=15,
         idealTempC=12, recommendedRhPct=90, typicalShelfLifeDays=10, q10=2.5,
         citation="USDA Agriculture Handbook 66 - chilling injury below 10 C"),
    dict(productId="BANANA", name="Banana", safeMinTempC=13, safeMaxTempC=16,
         idealTempC=14, recommendedRhPct=90, typicalShelfLifeDays=14, q10=2.5,
         citation="USDA Agriculture Handbook 66 - chilling injury below 13 C"),
    dict(productId="DATES", name="Dates", safeMinTempC=0, safeMaxTempC=5,
         idealTempC=0, recommendedRhPct=75, typicalShelfLifeDays=180, q10=2.0,
         citation="FAO date palm post-harvest guidance"),
)


def fetch_product_reference(out: Path) -> dict[str, Any]:
    rows = [{**p, "verified": "no",
             "source": "literature-recalled, pending extraction from the cited "
                       "open source"} for p in PRODUCT_REFERENCE]
    n = _write(out, rows, ["productId", "name", "safeMinTempC", "safeMaxTempC",
                           "idealTempC", "recommendedRhPct",
                           "typicalShelfLifeDays", "q10", "citation",
                           "verified", "source"])
    return {"ok": True, "rows": n, "warning": "every row is unverified"}


OFFLINE_FETCHERS = {
    "geonames_places": fetch_places,
    "public_holidays": fetch_holidays,
    "psychrometrics": fetch_psychrometrics,
    "product_reference": fetch_product_reference,
}
