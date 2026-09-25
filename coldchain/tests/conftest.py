"""Tests run against SQLite and an in-memory cache by default.

Point COLDCHAIN_TEST_DATABASE_URL at a real Postgres to run the same suite
against it — the Postgres path is exercised that way in CI and by hand before
the demo.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coldchain import cache                       # noqa: E402
from coldchain.db import session as db            # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database() -> str:
    url = os.environ.get("COLDCHAIN_TEST_DATABASE_URL")
    if not url:
        tmp = Path(tempfile.mkdtemp()) / "coldchain-test.db"
        url = f"sqlite:///{tmp}"
    backend = db.init(url)
    db.reset()
    return backend


@pytest.fixture(autouse=True)
def clean_cache():
    cache.init("")                                # force the memory backend
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pipeline():
    from coldchain.ingestion.pipeline import Pipeline

    return Pipeline(persist=False)


@pytest.fixture(autouse=True)
def release_platform_clock():
    """The simulated clock is global state.

    A runner takes it on its first tick and holds it until stopped, so a test
    that ticks without stopping leaves the next test's `clock.now()` frozen.
    Release it either side of every test rather than relying on each one to
    tidy up.
    """
    from coldchain import clock

    clock.uninstall()
    yield
    clock.uninstall()
