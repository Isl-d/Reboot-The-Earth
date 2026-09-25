"""Load the demo world into the database.

Reference rows come from coldchain/fleet.py so there is one definition of the
world, shared by the simulator, the seeder and the tests. Seeding is
idempotent: run it as often as you like.
"""
from __future__ import annotations

import hashlib
import json
import logging

from .. import fleet
from . import models, session as db

log = logging.getLogger("coldchain.seed")


def _stable_id(text: str) -> int:
    """A deterministic surrogate key, so seeding stays idempotent.

    Masked to 31 bits: the column is a plain INTEGER and the full eight hex
    digits overflow it.
    """
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16) & 0x7FFF_FFFF


def seed() -> dict[str, int]:
    counts = {"products": 0, "warehouses": 0, "stores": 0, "routes": 0,
              "trucks": 0, "devices": 0, "batches": 0, "inventory": 0}
    try:
        with db.session() as s:
            for p in fleet.PRODUCTS:
                s.merge(models.Product(**p))
                counts["products"] += 1
            for w in fleet.WAREHOUSES:
                s.merge(models.Warehouse(**w))
                counts["warehouses"] += 1
            for st in fleet.STORES:
                s.merge(models.Store(**st))
                counts["stores"] += 1
            for r in fleet.ROUTES:
                s.merge(models.Route(
                    id=r["id"], name=r["name"], origin_id=r["origin_id"],
                    destination_id=r["destination_id"],
                    distance_km=round(fleet.route_length_km(r), 3),
                    geometry=json.dumps(r["geometry"])))
                counts["routes"] += 1
            for b in fleet.BATCHES:
                s.merge(models.ProductBatch(**b))
                counts["batches"] += 1
                s.merge(models.Inventory(
                    # PYTHONHASHSEED is random per process, so hash() gave a
                    # different key each run and merge() inserted instead of
                    # updating - three seeds produced fifteen rows.
                    id=_stable_id(b["id"]),
                    batch_id=b["id"], location_id=b["truck_id"] or "WH01",
                    location_kind="TRUCK" if b["truck_id"] else "WAREHOUSE",
                    quantity_kg=b["quantity_kg"]))
                counts["inventory"] += 1
            for t in fleet.TRUCKS:
                s.merge(models.Truck(
                    id=t["id"], plate=t["plate"], status="IDLE",
                    route_id=t["route_id"], destination_id=t.get("destination_id"),
                    batch_id=t["batch_id"]))
                counts["trucks"] += 1
                s.merge(models.Device(id=fleet.device_id(t["id"]),
                                      truck_id=t["id"], kind="SIMULATED"))
                counts["devices"] += 1
            s.commit()
        log.info("seeded %s", counts)
    except Exception as exc:                            # noqa: BLE001 - demo safety
        log.warning("seeding failed (%s) - reference data still served from fleet.py", exc)
    return counts
