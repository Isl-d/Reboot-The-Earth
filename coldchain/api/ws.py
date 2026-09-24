"""The /ws/live hub.

Telemetry arrives on the MQTT thread; WebSocket sends must happen on the
asyncio loop. `broadcast()` is therefore thread-safe: it hands the message to
the loop with `call_soon_threadsafe` and returns immediately, so ingest is
never blocked by a slow client.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("coldchain.ws")


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[dict] | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue(maxsize=2000)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        log.info("ws client connected (%d total)", len(self.clients))

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    def broadcast(self, message: dict) -> None:
        """Called from any thread."""
        if self._loop is None or self._queue is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._enqueue, message)
        except RuntimeError:
            pass                                    # loop is shutting down

    def _enqueue(self, message: dict) -> None:
        assert self._queue is not None
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            # Better to drop one frame than to stall ingest behind a slow client.
            log.warning("ws queue full - dropping a frame")

    async def pump(self) -> None:
        """Fan messages out to every client. Runs as a background task."""
        assert self._queue is not None
        while True:
            message = await self._queue.get()
            dead: list[WebSocket] = []
            for ws in list(self.clients):
                try:
                    await ws.send_json(message)
                except Exception:                   # noqa: BLE001
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws)


hub = Hub()
