"""Latest truck state, in Redis (spec, section 7).

Keys, exactly as the brief lists them:

    truck:{id}:latest     the whole TruckState as JSON
    truck:{id}:risk       Person 4's risk, when one has been posted
    truck:{id}:location   {latitude, longitude, timestamp}

Redis holds current state so the map never has to scan the historical table.
It is a cache, not the record: `sensor_readings` in Postgres is authoritative,
and everything here carries a TTL.

If Redis is not reachable the same interface runs on a dictionary, so the demo
still works on a laptop with nothing installed. `backend()` says which is live.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from . import config

log = logging.getLogger("coldchain.cache")

_client: Any = None
_backend = "memory"
_mem: dict[str, str] = {}
_lock = threading.Lock()


def backend() -> str:
    """'redis' or 'memory'."""
    return _backend


def init(url: str | None = None) -> str:
    global _client, _backend
    url = config.REDIS_URL if url is None else url
    if not url:
        _client, _backend = None, "memory"
        return _backend
    try:
        import redis                                 # imported lazily on purpose

        c = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
        c.ping()
        _client, _backend = c, "redis"
        log.info("redis ready at %s", url)
    except Exception as exc:                          # noqa: BLE001 - demo safety
        log.warning("redis unavailable (%s) - latest state kept in memory", exc)
        _client, _backend = None, "memory"
    return _backend


def _set(key: str, value: str) -> None:
    if _client is not None:
        try:
            _client.set(key, value, ex=config.REDIS_TTL_S)
            return
        except Exception as exc:                      # noqa: BLE001
            log.warning("redis write failed (%s) - using memory", exc)
    with _lock:
        _mem[key] = value


def _get(key: str) -> Optional[str]:
    if _client is not None:
        try:
            value = _client.get(key)
            if value is not None:
                return value
            # Fall through: a write that failed mid-demo was parked in memory,
            # and returning None here would strand it.
        except Exception as exc:                      # noqa: BLE001
            log.warning("redis read failed (%s) - using memory", exc)
    with _lock:
        return _mem.get(key)


def _keys(pattern: str) -> list[str]:
    import fnmatch

    found: set[str] = set()
    if _client is not None:
        try:
            found.update(_client.scan_iter(match=pattern))
        except Exception:                             # noqa: BLE001
            pass
    with _lock:
        found.update(k for k in _mem if fnmatch.fnmatch(k, pattern))
    return sorted(found)


# ------------------------------------------------------------------ public
def set_latest(truck_id: str, state: dict) -> None:
    _set(f"truck:{truck_id}:latest", json.dumps(state, default=str))
    lat, lon = state.get("latitude"), state.get("longitude")
    if lat is not None and lon is not None:
        _set(f"truck:{truck_id}:location",
             json.dumps({"latitude": lat, "longitude": lon,
                         "timestamp": state.get("timestamp")}, default=str))


def get_latest(truck_id: str) -> Optional[dict]:
    raw = _get(f"truck:{truck_id}:latest")
    return json.loads(raw) if raw else None


def get_location(truck_id: str) -> Optional[dict]:
    raw = _get(f"truck:{truck_id}:location")
    return json.loads(raw) if raw else None


def set_risk(truck_id: str, risk: dict) -> None:
    """Person 4 owns these numbers; this platform only stores and serves them."""
    _set(f"truck:{truck_id}:risk", json.dumps(risk, default=str))


def get_risk(truck_id: str) -> Optional[dict]:
    raw = _get(f"truck:{truck_id}:risk")
    return json.loads(raw) if raw else None


def all_latest() -> list[dict]:
    out = []
    for key in _keys("truck:*:latest"):
        raw = _get(key)
        if raw:
            out.append(json.loads(raw))
    return sorted(out, key=lambda s: s.get("truckId") or s.get("truck_id") or "")


def clear() -> None:
    for key in _keys("truck:*"):
        if _client is not None:
            try:
                _client.delete(key)
                continue
            except Exception:                          # noqa: BLE001
                pass
        with _lock:
            _mem.pop(key, None)
    with _lock:
        _mem.clear()
