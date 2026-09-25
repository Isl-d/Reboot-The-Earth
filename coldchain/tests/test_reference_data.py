"""Reference data comes from the store once seeded.

The warehouse, store and batch tables were being seeded and then ignored: every
read served the hard-coded constants in fleet.py, so a column like
`available_capacity_kg` could never change — and that is precisely the column
Person 4 picks a destination by.

fleet.py remains the fallback, so the API still answers on a laptop with no
database.
"""
from __future__ import annotations

import pytest

from coldchain import fleet
from coldchain.db import models, queries, seed, session as db
from coldchain.ingestion.pipeline import Pipeline


@pytest.fixture
def seeded():
    db.reset()
    seed.seed()
    return True


@pytest.fixture
def empty():
    db.reset()
    return True


def test_seeded_reference_data_is_served_from_the_database(seeded):
    rows, source = queries.warehouses()
    assert source == "database"
    assert {w["id"] for w in rows} == {"WH01", "WH02", "WH03"}
    assert all("availableCapacityKg" in w for w in rows)


def test_an_empty_store_falls_back_to_fleet_py(empty):
    rows, source = queries.warehouses()
    assert source == "fallback"
    assert {w["id"] for w in rows} == {w["id"] for w in fleet.WAREHOUSES}
    # The fallback speaks the same dialect as the database path.
    assert all("availableCapacityKg" in w for w in rows)


def test_a_capacity_change_in_the_database_is_reflected(seeded):
    """The whole point: this column changes as stock moves."""
    before = queries.warehouse("WH01")["availableCapacityKg"]
    with db.session() as s:
        s.get(models.Warehouse, "WH01").available_capacity_kg = 42.0
        s.commit()

    after = queries.warehouse("WH01")["availableCapacityKg"]
    assert before != 42.0
    assert after == 42.0


def test_person_4_sees_the_changed_capacity(seeded):
    with db.session() as s:
        s.get(models.Warehouse, "WH01").available_capacity_kg = 17.0
        s.commit()

    bundle = Pipeline(persist=False).context_for("T102")
    wh01 = next(w for w in bundle["candidateWarehouses"] if w["id"] == "WH01")
    assert wh01["availableCapacityKg"] == 17.0


def test_the_person_4_bundle_still_works_with_no_database(empty):
    bundle = Pipeline(persist=False).context_for("T102")
    assert bundle["candidateWarehouses"]
    assert bundle["candidateWarehouses"][0]["id"] == "WH01"


def test_stores_and_batches_come_from_the_database_too(seeded):
    stores, s_source = queries.stores()
    batches, b_source = queries.batches()
    assert s_source == "database" and b_source == "database"
    assert {s["id"] for s in stores} == {s["id"] for s in fleet.STORES}
    assert queries.batch("CHK-1029")["quantityKg"] == 500


def test_a_batch_quantity_change_is_reflected(seeded):
    with db.session() as s:
        s.get(models.ProductBatch, "CHK-1029").quantity_kg = 250.0
        s.commit()
    assert queries.batch("CHK-1029")["quantityKg"] == 250.0


def test_unknown_ids_return_nothing(seeded):
    assert queries.warehouse("NOPE") is None
    assert queries.batch("NOPE") is None


def test_every_reference_row_is_camelcase(seeded):
    """Person 1 and 2 code against one spelling."""
    for rows, _ in (queries.warehouses(), queries.stores(), queries.batches()):
        for row in rows:
            assert not any("_" in key for key in row), row
