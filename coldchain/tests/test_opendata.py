"""The open-data layer: what it collects, and how honestly it reports it."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from coldchain.opendata import fetch, offline, sources


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch, "PROVENANCE", tmp_path / "provenance.json")
    return tmp_path


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------- catalogue
def test_every_source_declares_a_licence_and_a_url():
    assert sources.SOURCES
    for s in sources.SOURCES:
        assert s.licence.strip(), s.key
        assert s.url.startswith("http"), s.key
        assert s.provides.strip(), s.key
        assert s.access in ("offline", "network"), s.key


def test_source_keys_are_unique():
    keys = [s.key for s in sources.SOURCES]
    assert len(keys) == len(set(keys))


def test_no_source_is_proprietary():
    """The brief is open data only, so a closed licence is a bug."""
    banned = ("proprietary", "all rights reserved", "commercial licence")
    for s in sources.SOURCES:
        assert not any(b in s.licence.lower() for b in banned), s.key


def test_the_non_commercial_source_is_flagged():
    """FAO FLW is CC BY-NC-SA: usable here, not shippable commercially."""
    fao = sources.by_key("fao_food_loss")
    assert fao is not None
    assert "NC" in fao.licence
    assert "commercial" in fao.notes.lower()


def test_excluded_sources_are_named_with_a_reason():
    assert sources.EXCLUDED
    for name, why in sources.EXCLUDED:
        assert name and why


def test_every_offline_source_has_a_fetcher():
    for s in sources.by_access("offline"):
        assert s.key in offline.OFFLINE_FETCHERS, s.key


# --------------------------------------------------------------- places
def test_places_are_real_coordinates(data_dir):
    out = data_dir / "open_places.csv"
    result = offline.fetch_places(out)
    if not result["ok"]:
        pytest.skip(result["reason"])

    got = rows(out)
    assert got
    doha = next(r for r in got if r["name"] == "Doha")
    # Doha is at roughly 25.29 N, 51.53 E.
    assert 25.0 < float(doha["latitude"]) < 25.6
    assert 51.3 < float(doha["longitude"]) < 51.8
    assert int(doha["population"]) > 100_000
    assert "GeoNames" in doha["source"]


def test_every_place_carries_its_source(data_dir):
    out = data_dir / "open_places.csv"
    if not offline.fetch_places(out)["ok"]:
        pytest.skip("geonamescache not installed")
    assert all(r["source"] for r in rows(out))


# ------------------------------------------------------------- holidays
def test_holidays_cover_the_demo_years(data_dir):
    out = data_dir / "public_holidays.csv"
    result = offline.fetch_holidays(out)
    if not result["ok"]:
        pytest.skip(result["reason"])

    got = rows(out)
    assert got
    years = {r["date"][:4] for r in got}
    assert years <= {str(y) for y in offline.HOLIDAY_YEARS}
    assert all(r["countryCode"] in offline.COUNTRIES for r in got)


# -------------------------------------------------------- psychrometrics
def test_dew_point_matches_published_values():
    """30 C at 50 % RH has a dew point near 18.4 C."""
    assert offline.dew_point_c(30.0, 50.0) == pytest.approx(18.4, abs=0.2)
    # Saturated air condenses at its own temperature.
    assert offline.dew_point_c(20.0, 100.0) == pytest.approx(20.0, abs=0.05)


def test_dew_point_falls_as_the_air_dries():
    wet = offline.dew_point_c(35.0, 80.0)
    dry = offline.dew_point_c(35.0, 20.0)
    assert dry < wet < 35.0


def test_condensation_risk_is_the_question_a_door_opening_asks():
    # A Gulf afternoon: 41 C at 60 % RH wets a chilled pallet.
    assert offline.condensation_risk(2.0, 41.0, 60.0) is True
    # Dry desert air at the same temperature does not.
    assert offline.condensation_risk(2.0, 41.0, 5.0) is False


def test_the_psychrometric_table_is_internally_consistent(data_dir):
    out = data_dir / "psychrometrics.csv"
    offline.fetch_psychrometrics(out)
    for r in rows(out):
        dp = float(r["dewPointC"])
        assert dp <= float(r["airTempC"]) + 0.01     # never above the air
        assert r["condensesOn2CPallet"] == ("yes" if dp > 2.0 else "no")


# ---------------------------------------------------- product reference
def test_every_product_row_is_marked_unverified(data_dir):
    """These are transcribed, not downloaded. Saying so is the point."""
    out = data_dir / "product_reference.csv"
    offline.fetch_product_reference(out)
    got = rows(out)
    assert got
    for r in got:
        assert r["verified"] == "no"
        assert r["citation"].strip()


def test_product_temperature_bands_are_coherent(data_dir):
    out = data_dir / "product_reference.csv"
    offline.fetch_product_reference(out)
    for r in rows(out):
        lo, hi = float(r["safeMinTempC"]), float(r["safeMaxTempC"])
        ideal = float(r["idealTempC"])
        assert lo < hi, r["productId"]
        assert lo <= ideal <= hi, r["productId"]
        assert 0 <= float(r["recommendedRhPct"]) <= 100
        assert float(r["typicalShelfLifeDays"]) > 0
        assert float(r["q10"]) > 1.0


def test_chilling_sensitive_produce_is_not_stored_at_zero(data_dir):
    """Banana and tomato spoil from cold as readily as from heat."""
    out = data_dir / "product_reference.csv"
    offline.fetch_product_reference(out)
    by_id = {r["productId"]: r for r in rows(out)}
    assert float(by_id["BANANA"]["safeMinTempC"]) >= 12
    assert float(by_id["TOMATO"]["safeMinTempC"]) >= 7


# ------------------------------------------------------------ the run
def test_an_offline_run_collects_without_touching_the_network(data_dir):
    record = fetch.run(offline_only=True)

    for s in sources.by_access("offline"):
        assert record[s.key]["fetched"] is True, s.key
    for s in sources.by_access("network"):
        assert record[s.key]["fetched"] is False
        assert "offline" in record[s.key]["status"]


def test_provenance_records_licence_and_time(data_dir):
    fetch.run(offline_only=True)
    doc = json.loads((data_dir / "provenance.json").read_text())
    assert doc["generatedAt"]
    for key, entry in doc["sources"].items():
        assert entry["licence"], key
        assert entry["url"], key
        if entry["fetched"]:
            assert entry["fetchedAt"], key
            assert entry["rows"] is not None, key


def test_a_blocked_host_is_reported_not_hidden(data_dir, monkeypatch):
    """This environment blocks egress, and the run must say so plainly."""
    from coldchain.opendata import network

    def blocked(*_a, **_k):
        raise network.Blocked("overpass-api.de: 403 Forbidden")

    monkeypatch.setitem(network.NETWORK_FETCHERS, "osm_cold_sites", blocked)
    record = fetch.run(offline_only=False)

    entry = record["osm_cold_sites"]
    assert entry["fetched"] is False
    assert entry["status"] == "blocked"
    assert "overpass-api.de" in entry["reason"]


def test_a_blocked_network_does_not_stop_the_offline_sources(data_dir):
    record = fetch.run(offline_only=False)
    # Whatever the network did, these are local and must have landed.
    assert record["psychrometrics"]["fetched"] is True
    assert record["product_reference"]["fetched"] is True


# ------------------------------------------------- wired into the platform
def test_dew_point_reaches_the_truck_state():
    """The open psychrometrics are load-bearing, not shelf-ware."""
    from datetime import datetime, timezone

    from coldchain.ingestion.pipeline import Pipeline
    from coldchain.schemas import Telemetry

    p = Pipeline(persist=False)
    p.handle_reading(Telemetry(
        device_id="TRUCK-T102", truck_id="T102",
        timestamp=datetime(2026, 9, 25, 12, tzinfo=timezone.utc),
        temperature_c=41.0, humidity_pct=60.0, latitude=25.0, longitude=51.5,
        speed_kmh=0.0, g_force=0.2, door_open=True, refrigeration_on=True))

    t = next(x for x in p.fleet_states() if x.truck_id == "T102")
    assert t.derived.dew_point_c == pytest.approx(31.8, abs=0.5)
    assert t.derived.condensation_risk is True     # door open, warm humid air


def test_no_humidity_means_no_invented_dew_point():
    from datetime import datetime, timezone

    from coldchain.ingestion.pipeline import Pipeline
    from coldchain.schemas import Telemetry

    p = Pipeline(persist=False)
    p.handle_reading(Telemetry(
        device_id="TRUCK-T102", truck_id="T102",
        timestamp=datetime(2026, 9, 25, 12, tzinfo=timezone.utc),
        temperature_c=3.0, humidity_pct=None, latitude=25.0, longitude=51.5,
        speed_kmh=40.0, g_force=0.2, door_open=False, refrigeration_on=True))

    t = next(x for x in p.fleet_states() if x.truck_id == "T102")
    assert t.derived.dew_point_c is None
    assert t.derived.condensation_risk is None


def test_a_closed_door_is_not_a_condensation_risk():
    from datetime import datetime, timezone

    from coldchain.ingestion.pipeline import Pipeline
    from coldchain.schemas import Telemetry

    p = Pipeline(persist=False)
    p.handle_reading(Telemetry(
        device_id="TRUCK-T102", truck_id="T102",
        timestamp=datetime(2026, 9, 25, 12, tzinfo=timezone.utc),
        temperature_c=41.0, humidity_pct=60.0, latitude=25.0, longitude=51.5,
        speed_kmh=40.0, g_force=0.2, door_open=False, refrigeration_on=True))
    t = next(x for x in p.fleet_states() if x.truck_id == "T102")
    assert t.derived.dew_point_c is not None       # still reported
    assert t.derived.condensation_risk is False    # but sealed, so no risk
