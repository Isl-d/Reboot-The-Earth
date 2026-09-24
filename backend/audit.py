"""Tamper-evident decision log (CLAUDE.md section 7.6).

Every approved action is stored with the evidence it was based on, and each
record carries the hash of the record before it. Change any earlier entry and
`verify()` points at the exact record where the chain breaks.

This is a hash chain, not a blockchain: no network, no consensus, no coin. It
is the smallest thing that makes an audit trail checkable on one laptop.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from typing import Any

GENESIS = "0" * 64


def digest(prev_hash: str, seq: int, ts: float, kind: str, payload: dict[str, Any]) -> str:
    body = json.dumps({"seq": seq, "ts": round(ts, 3), "kind": kind, "payload": payload},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{prev_hash}{body}".encode()).hexdigest()


@dataclass
class Record:
    seq: int
    ts: float
    kind: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditLog:
    records: list[Record] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.records[-1].hash if self.records else GENESIS

    def append(self, kind: str, payload: dict[str, Any], ts: float | None = None) -> Record:
        ts = time.time() if ts is None else ts
        seq = len(self.records) + 1
        prev = self.head
        rec = Record(seq=seq, ts=ts, kind=kind, payload=payload, prev_hash=prev,
                     hash=digest(prev, seq, ts, kind, payload))
        self.records.append(rec)
        return rec

    def verify(self) -> tuple[bool, int | None]:
        """(chain intact, sequence number of the first broken record)."""
        prev = GENESIS
        for r in self.records:
            if r.prev_hash != prev or r.hash != digest(prev, r.seq, r.ts, r.kind, r.payload):
                return False, r.seq
            prev = r.hash
        return True, None

    def as_list(self) -> list[dict]:
        return [r.as_dict() for r in self.records]

    def reset(self) -> None:
        self.records.clear()
