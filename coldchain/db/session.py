"""Engine and session handling, with the demo's safety net built in.

Order of preference:
  1. PostgreSQL at COLDCHAIN_DATABASE_URL, with TimescaleDB if the extension
     is installable (sensor_readings becomes a hypertable).
  2. SQLite, if Postgres cannot be reached.

Losing the database on stage must never take the API down, so connecting is
best effort and the failure is logged once, loudly, rather than raised.
"""
from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .. import config
from .models import Base

log = logging.getLogger("coldchain.db")

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None
_backend = "none"
_timescale = False


def backend() -> str:
    """'postgresql', 'sqlite' or 'none'."""
    return _backend


def timescale_enabled() -> bool:
    return _timescale


def _try_postgres(url: str) -> Engine | None:
    try:
        eng = create_engine(url, pool_pre_ping=True, future=True)
        with eng.connect() as c:
            c.execute(text("select 1"))
        return eng
    except Exception as exc:                        # noqa: BLE001 - demo safety
        log.warning("postgres unavailable (%s) - falling back to sqlite", exc)
        return None


def _enable_timescale(eng: Engine) -> bool:
    """Make sensor_readings a hypertable when the extension is available."""
    try:
        with eng.begin() as c:
            c.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
            c.execute(text(
                "SELECT create_hypertable('sensor_readings', 'ts', "
                "if_not_exists => TRUE, migrate_data => TRUE)"))
        log.info("TimescaleDB hypertable enabled on sensor_readings")
        return True
    except Exception:                               # noqa: BLE001
        log.info("TimescaleDB not available - plain table with an index is fine")
        return False


def init(url: str | None = None, *, create: bool = True) -> str:
    """Connect, create the schema, and report which backend we ended up on."""
    global _engine, _Session, _backend, _timescale

    url = config.DATABASE_URL if url is None else url
    eng: Engine | None = None

    if url:
        if url.startswith("sqlite"):
            eng = create_engine(url, future=True,
                                connect_args={"check_same_thread": False})
            _backend = "sqlite"
        else:
            eng = _try_postgres(url)
            _backend = "postgresql" if eng is not None else "none"

    if eng is None:
        eng = create_engine("sqlite:///./coldchain.db", future=True,
                            connect_args={"check_same_thread": False})
        _backend = "sqlite"

    if create:
        Base.metadata.create_all(eng)
        if _backend == "postgresql":
            _timescale = _enable_timescale(eng)

    _engine = eng
    _Session = sessionmaker(bind=eng, expire_on_commit=False, future=True)
    log.info("database ready: %s%s", _backend,
             " + timescaledb" if _timescale else "")
    return _backend


def engine() -> Engine:
    if _engine is None:
        init()
    assert _engine is not None
    return _engine


def session() -> Session:
    if _Session is None:
        init()
    assert _Session is not None
    return _Session()


def reset() -> None:
    """Drop and recreate every table. Used by POST /api/simulation/reset."""
    eng = engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    if _backend == "postgresql":
        _enable_timescale(eng)
