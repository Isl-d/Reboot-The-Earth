"""Alembic environment for the ColdChain data platform.

The URL comes from COLDCHAIN_DATABASE_URL (via config.py) rather than
alembic.ini, so migrations run against whatever the service is pointed at
without editing a file.

`create_all` in session.py is what the demo uses to come up from nothing.
Migrations are how the schema changes once teammates have data they care
about: generate one with

    python -m alembic -c coldchain/alembic.ini revision --autogenerate -m "..."
    python -m alembic -c coldchain/alembic.ini upgrade head
"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coldchain import config as cc_config          # noqa: E402
from coldchain.db.models import Base               # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = cc_config.DATABASE_URL or "sqlite:///./coldchain.db"
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, compare_type=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True,
                          # SQLite cannot ALTER in place; batch mode rewrites
                          # the table instead, so one migration fits both.
                          render_as_batch=connection.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
