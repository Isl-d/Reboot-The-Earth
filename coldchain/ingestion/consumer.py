"""MQTT consumer: Mosquitto -> pipeline.

Subscribes to `coldchain/trucks/+/telemetry` and `+/events`, hands each
message to the pipeline, and reconnects on its own. A broker that goes away
mid-demo must not take the API with it, so every failure here is logged and
retried rather than raised.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from .. import config
from .pipeline import Pipeline

log = logging.getLogger("coldchain.consumer")


class MqttConsumer:
    def __init__(self, pipeline: Pipeline, *, host: str = config.MQTT_HOST,
                 port: int = config.MQTT_PORT,
                 client_id: str = config.MQTT_CLIENT_ID) -> None:
        self.pipeline = pipeline
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.messages = 0
        self._client: Any = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Connect and start the network loop. False if the broker is absent."""
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            log.warning("paho-mqtt is not installed - MQTT ingest disabled")
            return False

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                 client_id=self.client_id)
            client.on_connect = self._on_connect_v2
        except (AttributeError, TypeError):             # paho 1.x
            client = mqtt.Client(client_id=self.client_id)
            client.on_connect = self._on_connect_v1

        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        client.reconnect_delay_set(min_delay=1, max_delay=8)
        try:
            client.connect(self.host, self.port, keepalive=30)
        except Exception as exc:                        # noqa: BLE001 - demo safety
            # Say it and mean it: connect_async plus a running network loop is
            # what actually retries. Before this the message promised a retry
            # and nothing retried, so a broker that came up a second late left
            # MQTT ingest dead for the life of the process.
            log.warning("broker at %s:%s unreachable (%s) - retrying in the "
                        "background", self.host, self.port, exc)
            try:
                client.connect_async(self.host, self.port, keepalive=30)
                client.loop_start()
                self._client = client
            except Exception as retry_exc:              # noqa: BLE001
                log.warning("could not arm the reconnect loop: %s", retry_exc)
            return False

        client.loop_start()
        self._client = client
        return True

    def stop(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:                           # noqa: BLE001
                pass
            self._client = None
        self.connected = False

    # ------------------------------------------------------------ callbacks
    def _subscribe(self, client: Any) -> None:
        client.subscribe([(config.TELEMETRY_WILDCARD, 0),
                          (config.EVENTS_WILDCARD, 0)])
        log.info("subscribed to %s and %s", config.TELEMETRY_WILDCARD,
                 config.EVENTS_WILDCARD)

    def _on_connect_v2(self, client, userdata, flags, reason_code, properties=None):
        self.connected = True
        self._subscribe(client)

    def _on_connect_v1(self, client, userdata, flags, rc):
        self.connected = True
        self._subscribe(client)

    def _on_disconnect(self, *args: Any) -> None:
        self.connected = False
        log.warning("broker disconnected - paho will retry")

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        with self._lock:
            self.messages += 1
        try:
            payload = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError) as exc:
            log.warning("undecodable message on %s: %s", msg.topic, exc)
            return
        if msg.topic.endswith("/telemetry"):
            self.pipeline.handle_payload(payload, topic=msg.topic)
        elif msg.topic.endswith("/events"):
            self.pipeline.handle_event_payload(payload, topic=msg.topic)
