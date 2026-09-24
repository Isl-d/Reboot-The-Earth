"""The publisher must never fail silently.

This pins a bug found by running the service for real: paho's `publish()` on
a disconnected client returns MQTT_ERR_NO_CONN instead of raising, so the
simulator went on ticking while nothing reached the broker. The dashboard
froze with no error anywhere — the worst possible failure on stage.
"""
from __future__ import annotations

import socket

import pytest

from coldchain import config
from coldchain.simulator.runner import MqttPublisher


def broker_up() -> bool:
    try:
        socket.create_connection((config.MQTT_HOST, config.MQTT_PORT),
                                 timeout=1).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not broker_up(),
                                reason="no MQTT broker on localhost:1883")


def test_a_successful_publish_is_counted():
    pub = MqttPublisher()
    try:
        pub("coldchain/trucks/T102/telemetry", {"truckId": "T102"})
        assert pub.published == 1
        assert pub.failed == 0
        assert pub.last_error is None
    finally:
        pub.stop()


def test_publishing_after_the_broker_is_gone_is_counted_as_a_failure():
    pub = MqttPublisher()
    pub.stop()                       # simulate the connection going away
    pub("coldchain/trucks/T102/telemetry", {"truckId": "T102"})
    assert pub.failed >= 1
    assert pub.last_error is not None      # the stall is visible, not silent


def test_stats_expose_enough_to_diagnose_a_stall():
    pub = MqttPublisher()
    try:
        stats = pub.stats()
        for key in ("connected", "published", "failed", "lastError", "clientId"):
            assert key in stats
    finally:
        pub.stop()


def test_each_publisher_gets_its_own_client_id():
    """A fixed id makes two instances evict each other in a loop."""
    a, b = MqttPublisher(), MqttPublisher()
    try:
        assert a.client_id != b.client_id
    finally:
        a.stop()
        b.stop()
