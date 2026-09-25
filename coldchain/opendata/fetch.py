"""Collect every open data source the fleet needs.

    python -m coldchain.opendata.fetch              # everything reachable
    python -m coldchain.opendata.fetch --offline    # no network attempts
    python -m coldchain.opendata.fetch --list       # the catalogue and licences

Offline sources always run: they ship inside open-source packages and need no
egress. Network sources are attempted unless --offline, and a blocked host is
reported rather than retried around.

Nothing is silently assumed. `coldchain/data/provenance.json` records, per
source, whether it actually arrived, when, how many rows, and under what
licence — so any number on the dashboard can be traced to what produced it.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import network, offline, sources

log = logging.getLogger("coldchain.opendata")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROVENANCE = DATA_DIR / "provenance.json"


def _points() -> list[dict[str, Any]]:
    """The coordinates weather is pulled for: one per route destination."""
    from .. import fleet

    pts = [{"id": w["id"], "latitude": w["latitude"], "longitude": w["longitude"]}
           for w in fleet.WAREHOUSES]
    pts += [{"id": s["id"], "latitude": s["latitude"], "longitude": s["longitude"]}
            for s in fleet.STORES]
    return pts


def _legs() -> list[dict[str, Any]]:
    """Origin/destination pairs for routing, from the demo world."""
    from .. import fleet

    legs = []
    for r in fleet.ROUTES:
        origin = fleet.place_by_id(r["origin_id"])
        dest = fleet.place_by_id(r["destination_id"])
        if origin is None or dest is None:
            continue
        legs.append({"id": r["id"], "name": r["name"],
                     "fromId": origin.id, "fromLat": origin.lat, "fromLon": origin.lon,
                     "toId": dest.id, "toLat": dest.lat, "toLon": dest.lon})
    return legs


def run(*, offline_only: bool = False) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {}

    for src in sources.SOURCES:
        entry: dict[str, Any] = {
            "name": src.name,
            "category": src.category,
            "licence": src.licence,
            "url": src.url,
            "access": src.access,
            "output": src.output,
            "fetched": False,
        }
        out = DATA_DIR / src.output if src.output else None

        if src.access == "offline":
            fn = offline.OFFLINE_FETCHERS.get(src.key)
            if fn is None or out is None:
                entry["status"] = "no fetcher"
            else:
                result = fn(out)
                entry.update(status="ok" if result.get("ok") else "failed",
                             fetched=bool(result.get("ok")),
                             rows=result.get("rows"))
                if result.get("reason"):
                    entry["reason"] = result["reason"]
                if result.get("warning"):
                    entry["warning"] = result["warning"]

        elif offline_only:
            entry["status"] = "skipped (--offline)"

        else:
            fn = network.NETWORK_FETCHERS.get(src.key)
            if fn is None or out is None:
                entry["status"] = "no fetcher yet"
            else:
                try:
                    if src.key == "osrm_routes":
                        result = fn(out, _legs())
                    elif src.key in ("open_meteo_forecast", "open_meteo_archive"):
                        result = fn(out, _points())
                    else:
                        result = fn(out)
                    entry.update(status="ok", fetched=True,
                                 rows=result.get("rows"))
                except network.Blocked as exc:
                    entry.update(status="blocked", reason=str(exc))
                    log.warning("%s: blocked (%s)", src.key, exc)
                except Exception as exc:              # noqa: BLE001
                    entry.update(status="error", reason=str(exc))
                    log.warning("%s: %s", src.key, exc)

        if entry["fetched"]:
            entry["fetchedAt"] = datetime.now(timezone.utc).isoformat()
        record[src.key] = entry

    PROVENANCE.write_text(json.dumps(
        {"generatedAt": datetime.now(timezone.utc).isoformat(),
         "sources": record}, indent=2, ensure_ascii=False))
    return record


def print_catalogue() -> None:
    print(f"{len(sources.SOURCES)} open sources for cold-chain logistics\n")
    for cat in sources.categories():
        print(f"  {cat.upper()}")
        for s in sources.SOURCES:
            if s.category != cat:
                continue
            mark = "offline" if s.access == "offline" else "network"
            print(f"    [{mark}] {s.name}")
            print(f"             {s.provides}")
            print(f"             licence: {s.licence}")
        print()
    print("  DELIBERATELY EXCLUDED (not openly licensed)")
    for name, why in sources.EXCLUDED:
        print(f"    {name}: {why}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true",
                    help="do not attempt any network source")
    ap.add_argument("--list", action="store_true",
                    help="print the catalogue and exit")
    args = ap.parse_args()

    if args.list:
        print_catalogue()
        return

    record = run(offline_only=args.offline)

    got = [k for k, v in record.items() if v["fetched"]]
    blocked = [k for k, v in record.items() if v["status"] == "blocked"]
    other = [k for k, v in record.items()
             if not v["fetched"] and v["status"] != "blocked"]

    print(f"\nfetched {len(got)}/{len(record)} sources")
    for k in got:
        rows = record[k].get("rows")
        warn = record[k].get("warning")
        print(f"  ok       {k:24} {rows if rows is not None else ''} rows"
              + (f"  ({warn})" if warn else ""))
    for k in blocked:
        print(f"  blocked  {k:24} {record[k]['reason']}")
    for k in other:
        print(f"  --       {k:24} {record[k]['status']}")
    print(f"\nprovenance written to {PROVENANCE}")


if __name__ == "__main__":
    main()
