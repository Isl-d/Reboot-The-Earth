"""PostgreSQL persistence, with the demo's safety net built in.

If COLDGUARD_DB_URL is empty, or Postgres is not reachable, ColdGuard keeps
running entirely in memory and says so once in the log. Losing the database on
stage must never take the dashboard down, so every write here is best effort.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import threading
from typing import Any, Iterable

from . import config

log = logging.getLogger("coldguard.db")


def _iso(ts: float | None) -> dt.datetime | None:
    if ts is None:
        return None
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc)


class Database:
    """Thin wrapper around psycopg. Every method is a no-op when disabled."""

    def __init__(self, url: str = "") -> None:
        self.url = url or config.DB_URL
        self.conn = None
        self.enabled = False
        self._lock = threading.Lock()
        self._warned = False

    # ------------------------------------------------------------- lifecycle
    def connect(self) -> bool:
        if not self.url:
            log.info("no COLDGUARD_DB_URL set - running in memory only")
            return False
        try:
            import psycopg
            self.conn = psycopg.connect(self.url, autocommit=True)
            self.enabled = True
            log.info("connected to PostgreSQL")
            self.migrate()
            return True
        except Exception as exc:                       # pragma: no cover - demo safety
            log.warning("PostgreSQL unavailable (%s) - running in memory only", exc)
            self.enabled = False
            return False

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn, self.enabled = None, False

    def _exec(self, sql: str, params: Iterable[Any] = ()) -> None:
        if not self.enabled:
            return
        try:
            with self._lock, self.conn.cursor() as cur:
                cur.execute(sql, tuple(params))
        except Exception as exc:                       # pragma: no cover - demo safety
            if not self._warned:
                log.warning("database write failed, continuing in memory: %s", exc)
                self._warned = True

    def fetch(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        if not self.enabled:
            return []
        try:
            with self._lock, self.conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                return cur.fetchall()
        except Exception:                              # pragma: no cover - demo safety
            return []

    # --------------------------------------------------------------- schema
    def migrate(self) -> None:
        here = config.ROOT / "backend"
        self._exec((here / "schema.sql").read_text())
        self._exec((here / "seed.sql").read_text())
        self.seed_reference_data()

    def seed_reference_data(self) -> None:
        """products and places come straight from data/*.csv."""
        with open(config.DATA_DIR / "products.csv", newline="") as f:
            for r in csv.DictReader(f):
                self._exec(
                    """INSERT INTO products VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (product) DO UPDATE SET
                       ideal_temp_c=EXCLUDED.ideal_temp_c,
                       life_at_ideal_days=EXCLUDED.life_at_ideal_days,
                       q10=EXCLUDED.q10, alert_limit_c=EXCLUDED.alert_limit_c,
                       min_life_on_arrival_days=EXCLUDED.min_life_on_arrival_days,
                       value_qar_per_kg=EXCLUDED.value_qar_per_kg""",
                    (r["product"], r["ideal_temp_c"], r["life_at_ideal_days"], r["q10"],
                     r["alert_limit_c"], r["min_life_on_arrival_days"],
                     r["value_qar_per_kg"], r.get("source_note", "")))
        with open(config.DATA_DIR / "places.csv", newline="") as f:
            for r in csv.DictReader(f):
                self._exec(
                    """INSERT INTO places VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (place_id) DO UPDATE SET
                       name=EXCLUDED.name, type=EXCLUDED.type, lat=EXCLUDED.lat,
                       lon=EXCLUDED.lon, has_cold_room=EXCLUDED.has_cold_room,
                       source=EXCLUDED.source""",
                    (r["place_id"], r["name"], r["type"], r["lat"], r["lon"],
                     str(r["has_cold_room"]).strip().lower() == "true", r.get("source", "")))

    # --------------------------------------------------------------- writes
    def upsert_shipment(self, truck_id: str, product: str, qty_kg: float, route_id: str,
                        destination_place_id: str, eta: float | None, life_left_h: float,
                        status: str) -> None:
        self._exec(
            """INSERT INTO shipments VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (truck_id) DO UPDATE SET
               product=EXCLUDED.product, qty_kg=EXCLUDED.qty_kg, route_id=EXCLUDED.route_id,
               destination_place_id=EXCLUDED.destination_place_id, eta=EXCLUDED.eta,
               life_left_h=EXCLUDED.life_left_h, status=EXCLUDED.status""",
            (truck_id, product, qty_kg, route_id, destination_place_id, _iso(eta),
             life_left_h, status))

    def insert_reading(self, r: dict[str, Any]) -> None:
        self._exec(
            "INSERT INTO readings VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (_iso(r["ts"]), r["truck_id"], r.get("air_c"), r.get("hum_pct"),
             r.get("door_open"), r.get("lat"), r.get("lon"), r.get("src")))

    def insert_event(self, e: dict[str, Any]) -> None:
        self._exec(
            "INSERT INTO events (truck_id,type,started_at,ended_at,peak_c,note) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (e["truck_id"], e["type"], _iso(e["started_at"]), _iso(e.get("ended_at")),
             e.get("peak_c"), e.get("note")))

    def insert_decision(self, d: dict[str, Any]) -> None:
        self._exec(
            """INSERT INTO decisions (decision_id,truck_id,product,qty_kg,options,facts,
                                      chosen,text_en,text_ar,text_source,created_at,
                                      prev_hash,hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (decision_id) DO NOTHING""",
            (d["decision_id"], d["truck_id"], d.get("product"), d.get("qty_kg"),
             json.dumps(d["options"]), json.dumps(d["facts"]), d.get("chosen"),
             d.get("text_en"), d.get("text_ar"), d.get("text_source"),
             _iso(d["created_at"]), d["prev_hash"], d["hash"]))

    def approve_decision(self, decision_id: str, chosen: str, by: str, at: float,
                         prev_hash: str, hash_: str) -> None:
        self._exec(
            "UPDATE decisions SET chosen=%s, approved_by=%s, approved_at=%s, "
            "prev_hash=%s, hash=%s WHERE decision_id=%s",
            (chosen, by, _iso(at), prev_hash, hash_, decision_id))

    def clear_run_data(self) -> None:
        if not self.enabled:
            return
        self._exec((config.ROOT / "backend" / "seed.sql").read_text())


db = Database()
