"""One clock for the whole platform.

By default this is the wall clock. When the simulator runs accelerated, it
installs a simulated clock and advances it by the same dt it steps the trucks
with, so three things stay consistent with each other:

* the timestamps on the telemetry,
* the durations the derived values accumulate (time above threshold, door
  open duration), and
* the `now` that validation compares a timestamp against.

Without this, a demo at x10 would emit ten minutes of readings that all carry
the same wall-clock second, and no duration-based incident would ever open.

The simulated clock only diverges from wall time when the speed multiplier is
greater than one. At x1 it tracks real time, so a separate ingest process
reading the same stream sees no skew.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone


class SimulatedClock:
    """A clock the simulator advances by hand."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime.now(timezone.utc)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def advance(self, seconds: float) -> datetime:
        with self._lock:
            self._now += timedelta(seconds=seconds)
            return self._now


_simulated: SimulatedClock | None = None


def now() -> datetime:
    """The current time, simulated or real."""
    return _simulated.now() if _simulated is not None else datetime.now(timezone.utc)


def install(clock: SimulatedClock) -> None:
    global _simulated
    _simulated = clock


def uninstall() -> None:
    global _simulated
    _simulated = None


def is_simulated() -> bool:
    return _simulated is not None
