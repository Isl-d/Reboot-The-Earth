"""The Alembic baseline must match the models.

`create_all` is how the demo comes up from nothing; migrations are how the
schema changes once teammates have data they care about. If the two drift, a
migration silently stops producing the schema the code expects — so this
builds a database from the migration alone and compares it against the
metadata.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from coldchain.db.models import Base

ROOT = Path(__file__).resolve().parents[2]
INI = ROOT / "coldchain" / "alembic.ini"


def alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    import os

    env = {**os.environ, "COLDCHAIN_DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(INI), *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)


@pytest.fixture
def migrated(tmp_path) -> str:
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    r = alembic(url, "upgrade", "head")
    assert r.returncode == 0, f"upgrade failed:\n{r.stdout}\n{r.stderr}"
    return url


def test_the_migration_creates_every_table_the_models_declare(migrated):
    eng = create_engine(migrated)
    tables = set(inspect(eng).get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables), (
        f"missing: {set(Base.metadata.tables) - tables}, "
        f"unexpected: {tables - set(Base.metadata.tables)}")


def test_every_table_has_the_columns_the_models_declare(migrated):
    eng = create_engine(migrated)
    insp = inspect(eng)
    for name, table in Base.metadata.tables.items():
        built = {c["name"] for c in insp.get_columns(name)}
        declared = {c.name for c in table.columns}
        assert declared <= built, f"{name} is missing {declared - built}"


def test_sensor_readings_is_indexed_for_time_series_queries(migrated):
    eng = create_engine(migrated)
    indexes = inspect(eng).get_indexes("sensor_readings")
    columns = {tuple(i["column_names"]) for i in indexes}
    # The query pattern is "recent readings for one truck".
    assert ("truck_id", "ts") in columns or (
        ("truck_id",) in columns and ("ts",) in columns)


def test_the_migration_downgrades_cleanly(tmp_path):
    url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    assert alembic(url, "upgrade", "head").returncode == 0
    r = alembic(url, "downgrade", "base")
    assert r.returncode == 0, f"downgrade failed:\n{r.stdout}\n{r.stderr}"

    eng = create_engine(url)
    left = set(inspect(eng).get_table_names()) - {"alembic_version"}
    assert left == set(), f"downgrade left tables behind: {left}"


def test_autogenerate_finds_no_drift_against_the_models(migrated):
    """The real check: after upgrading, alembic should see nothing to do."""
    r = alembic(migrated, "check")
    if r.returncode != 0 and "No such command" in (r.stderr or ""):
        pytest.skip("this alembic is too old for `alembic check`")
    assert r.returncode == 0, (
        "the models and the migration have drifted; generate a revision:\n"
        f"{r.stdout}\n{r.stderr}")
