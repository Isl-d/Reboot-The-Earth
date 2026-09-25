"""Drives the simulated fleet and publishes telemetry.

Two sinks, same physics:

* MQTT — the real path. Publishes to `coldchain/trucks/{id}/telemetry`, which
  the consumer subscribes to. This is what runs on stage.
* Direct — hands each payload straight to a Pipeline. No broker needed, so a
  laptop with nothing installed still runs the whole demo, and the tests can
  drive a hundred ticks without a network.

The runner is a thread the API starts and stops through /api/simulation/*.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from typing import Any, Callable, Optional

from .. import clock, config
from . import scenarios

log = logging.getLogger("coldchain.simulator")

Sink = Callable[[str, dict], None]                     # (topic, payload)


class SimulationRunner:
    def __init__(self, *, sink: Sink, seed: int = config.SIM_SEED,
                 tick_s: float = config.TICK_SECONDS) -> None:
        self.sink = sink
        self.seed = seed
        self.tick_s = tick_s
        self.speed_multiplier = 1.0
        self.trucks = scenarios.build_fleet(seed)
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self.ticks = 0
        # The simulated clock exists only while the simulation is driving
        # time. Installing it in the constructor froze clock.now() for the
        # life of the process: an idle service rejected a real device's
        # correctly-stamped telemetry as `timestamp_in_future` once uptime
        # passed the skew limit, and every timestamp-less reading shared one
        # instant so no duration-based incident could open.
        self._clock: clock.SimulatedClock | None = None

    # ------------------------------------------------------------ control
    def _install_clock(self) -> None:
        """Take over the platform clock, anchored at the real time now."""
        self._clock = clock.SimulatedClock()
        clock.install(self._clock)

    def _release_clock(self) -> None:
        """Hand the platform back to the wall clock."""
        self._clock = None
        clock.uninstall()

    def start(self, speed_multiplier: float = 1.0) -> bool:
        """Start ticking. Returns False if it was already running."""
        with self._lock:
            if self.running:
                self.speed_multiplier = speed_multiplier
                return False
            self.speed_multiplier = speed_multiplier
            self._install_clock()
            self._stop.clear()
            self.running = True
            self._thread = threading.Thread(target=self._loop, name="coldchain-sim",
                                            daemon=True)
            self._thread.start()
            log.info("simulation started (x%s)", speed_multiplier)
            return True

    def stop(self) -> bool:
        with self._lock:
            was_running = self.running
            if was_running:
                self._stop.set()
                self.running = False

        # Join before releasing the clock. A tick already waiting on the lock
        # would otherwise reinstall it the moment we let go, and time would
        # stay frozen for every real device after the demo stopped.
        if self._thread is not None:
            self._thread.join(timeout=3)

        with self._lock:
            # Released even if we were never started: a hand-driven tick takes
            # the clock too.
            self._release_clock()

        if not was_running:
            return False
        log.info("simulation stopped after %d ticks", self.ticks)
        return True

    def reset(self) -> None:
        was_running = self.running
        self.stop()
        with self._lock:
            self.trucks = scenarios.build_fleet(self.seed)
            self.ticks = 0
            self._release_clock()
        if was_running:
            self.start(self.speed_multiplier)

    def set_scenario(self, truck_id: str, scenario: str,
                     speed_multiplier: float | None = None) -> bool:
        with self._lock:
            truck = self.trucks.get(truck_id)
            if truck is None:
                return False
            truck.set_scenario(scenario)
            if speed_multiplier:
                self.speed_multiplier = speed_multiplier
        log.info("%s -> %s", truck_id, scenario)
        return True

    def scenario_of(self, truck_id: str) -> str:
        t = self.trucks.get(truck_id)
        return t.scenario if t else scenarios.NORMAL

    # --------------------------------------------------------------- loop
    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self.tick_s)

    def tick(self) -> list[dict]:
        """One round of telemetry from every truck. Also the test entry point."""
        with self._lock:
            trucks = list(self.trucks.values())
            dt = self.tick_s * max(0.1, self.speed_multiplier)
            self.ticks += 1
            # A tick drives time even when nobody called start() - the demo
            # panel and the tests step by hand - so take the clock now if we
            # do not already hold it.
            if self._clock is None:
                self._install_clock()
            # Move the platform clock with the simulation, so timestamps,
            # accumulated durations and validation all agree (clock.py).
            self._clock.advance(dt)

        payloads = []
        for truck in trucks:
            payload = truck.step(dt)
            payloads.append(payload)

            # Events first: a door that just opened explains the reading that
            # follows it, and arriving after would read as a contradiction.
            events_topic = config.EVENTS_TOPIC.format(truck_id=truck.truck_id)
            for event in truck.drain_events():
                try:
                    self.sink(events_topic, event)
                except Exception as exc:               # noqa: BLE001
                    log.warning("event publish failed for %s: %s",
                                truck.truck_id, exc)

            topic = config.TELEMETRY_TOPIC.format(truck_id=truck.truck_id)
            try:
                self.sink(topic, payload)
            except Exception as exc:                   # noqa: BLE001
                log.warning("publish failed for %s: %s", truck.truck_id, exc)
        return payloads


# ---------------------------------------------------------------- sinks
def direct_sink(pipeline: Any) -> Sink:
    """Feed the pipeline in-process; no broker involved.

    Routes by topic exactly as the MQTT consumer does. Without this an event
    would be handed to the telemetry path and rejected for having no
    temperature — the no-broker mode has to behave like the real one.
    """
    def sink(topic: str, payload: dict) -> None:
        if topic.endswith("/events"):
            pipeline.handle_event_payload(payload, topic=topic)
        else:
            pipeline.handle_payload(payload, topic=topic)
    return sink


class MqttPublisher:
    """Publishes telemetry to Mosquitto, and says so when it cannot.

    paho's `publish()` on a disconnected client does not raise: it returns
    `MQTT_ERR_NO_CONN` and drops the message. Ignoring that return value turns
    a dead publisher into a silently frozen dashboard, with the simulator
    still ticking happily — so every result is checked here and the failures
    are counted and surfaced through /api/health.
    """

    def __init__(self, host: str = config.MQTT_HOST, port: int = config.MQTT_PORT,
                 client_id: str | None = None) -> None:
        import paho.mqtt.client as mqtt

        # A fixed client id means a second instance evicts the first and the
        # two thrash. Unique per process unless the caller insists.
        self.client_id = client_id or f"coldchain-sim-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.host, self.port = host, port
        self.connected = False
        self.published = 0
        self.failed = 0
        self.last_error: str | None = None

        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                       client_id=self.client_id)
            self._client.on_connect = lambda c, u, f, rc, p=None: self._up()
        except (AttributeError, TypeError):            # paho 1.x
            self._client = mqtt.Client(client_id=self.client_id)
            self._client.on_connect = lambda c, u, f, rc: self._up()
        self._client.on_disconnect = lambda *a: self._down()
        # Keep trying rather than giving up after the first drop.
        self._client.reconnect_delay_set(min_delay=1, max_delay=8)
        self._client.connect(host, port, keepalive=30)
        self._client.loop_start()

    def _up(self) -> None:
        self.connected = True
        log.info("publisher connected to %s:%s as %s", self.host, self.port,
                 self.client_id)

    def _down(self) -> None:
        self.connected = False
        log.warning("publisher lost the broker - paho will retry")

    def __call__(self, topic: str, payload: dict) -> None:
        import paho.mqtt.client as mqtt

        info = self._client.publish(topic, json.dumps(payload), qos=0)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            self.failed += 1
            self.last_error = f"rc={info.rc} on {topic}"
            # One line per stall, not one per message.
            if self.failed == 1 or self.failed % 50 == 0:
                log.warning("publish failed (%s) - %d dropped so far",
                            self.last_error, self.failed)
            return
        self.published += 1

    def stop(self) -> None:
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:                              # noqa: BLE001
            pass

    def stats(self) -> dict:
        return {"connected": self.connected, "published": self.published,
                "failed": self.failed, "lastError": self.last_error,
                "clientId": self.client_id}


def mqtt_sink(host: str = config.MQTT_HOST, port: int = config.MQTT_PORT,
              client_id: str | None = None) -> MqttPublisher:
    """Publish to Mosquitto, the real path."""
    return MqttPublisher(host, port, client_id)
