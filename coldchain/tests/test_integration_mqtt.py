"""The real path, end to end: simulator -> Mosquitto -> consumer -> pipeline.

Skipped automatically when no broker is listening, so the suite still runs on
a laptop with nothing installed. Run a broker and these execute:

    mosquitto -c coldchain/mosquitto/mosquitto.conf
"""
from __future__ import annotations

import socket
import time

import pytest

from coldchain import config
from coldchain.ingestion.consumer import MqttConsumer
from coldchain.ingestion.pipeline import Pipeline
from coldchain.simulator import scenarios
from coldchain.simulator.runner import SimulationRunner, mqtt_sink


def broker_up() -> bool:
    try:
        socket.create_connection((config.MQTT_HOST, config.MQTT_PORT),
                                 timeout=1).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not broker_up(),
                                reason="no MQTT broker on localhost:1883")


def wait_for(predicate, timeout=10.0, interval=0.1):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


@pytest.fixture
def wired():
    pipeline = Pipeline(persist=False)
    consumer = MqttConsumer(pipeline, client_id="coldchain-test-consumer")
    assert consumer.start(), "consumer could not reach the broker"
    assert wait_for(lambda: consumer.connected), "consumer never connected"
    # 5 simulated seconds per tick, so a 40-tick run covers 200 s and clears
    # the 60 s incident thresholds in config.py.
    runner = SimulationRunner(sink=mqtt_sink(client_id="coldchain-test-sim"),
                              tick_s=5.0)
    yield pipeline, consumer, runner
    runner.stop()
    consumer.stop()


def test_telemetry_crosses_the_broker_and_lands_in_the_pipeline(wired):
    pipeline, consumer, runner = wired
    runner.tick()

    assert wait_for(lambda: consumer.messages >= len(runner.trucks)), \
        f"only {consumer.messages} messages arrived"
    assert wait_for(lambda: any(t.temperature_c is not None
                                for t in pipeline.fleet_states()))

    t102 = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert t102.temperature_c is not None
    assert t102.latitude is not None
    assert pipeline.rejected == []


def test_a_refrigeration_failure_reaches_the_pipeline_over_mqtt(wired):
    pipeline, consumer, runner = wired
    runner.set_scenario("T102", scenarios.REFRIGERATION_FAILURE)
    for _ in range(40):
        runner.tick()

    assert wait_for(lambda: any(
        i.type == "REFRIGERATION_FAILURE" for i in pipeline.all_incidents()),
        timeout=15), "no refrigeration incident arrived over the broker"

    t102 = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert t102.refrigeration_on is False
    assert t102.temperature_c > 4.0


def test_a_malformed_message_is_rejected_not_crashed(wired):
    import json

    import paho.mqtt.publish as publish

    pipeline, consumer, runner = wired
    topic = config.TELEMETRY_TOPIC.format(truck_id="T102")

    publish.single(topic, json.dumps({"truckId": "T102", "temperatureC": -127.0,
                                      "latitude": 25.0, "longitude": 51.0}),
                   hostname=config.MQTT_HOST, port=config.MQTT_PORT)
    assert wait_for(lambda: any(r["reason"] == "temperature_out_of_range"
                                for r in pipeline.rejected))

    # Not JSON at all: logged and ignored, the consumer stays up.
    publish.single(topic, "this is not json", hostname=config.MQTT_HOST,
                   port=config.MQTT_PORT)
    time.sleep(0.5)
    runner.tick()
    assert wait_for(lambda: consumer.connected)


def test_device_events_cross_the_broker_too(wired):
    """The events topic was subscribed and discarded until now."""
    import json

    import paho.mqtt.publish as publish

    pipeline, consumer, runner = wired
    topic = config.EVENTS_TOPIC.format(truck_id="T102")
    publish.single(topic, json.dumps({"truckId": "T102", "type": "DOOR_OPENED",
                                      "detail": "lid lifted"}),
                   hostname=config.MQTT_HOST, port=config.MQTT_PORT)

    assert wait_for(lambda: any(e.type == "DOOR_OPENED"
                                for e in pipeline.device_events())), \
        "no device event arrived over the broker"
    t = next(x for x in pipeline.fleet_states() if x.truck_id == "T102")
    assert t.door_open is True
    assert pipeline.rejected == []


def test_the_simulator_publishes_events_over_the_broker(wired):
    pipeline, consumer, runner = wired
    runner.set_scenario("T102", scenarios.REFRIGERATION_FAILURE)
    runner.tick()

    assert wait_for(lambda: any(e.type == "REFRIGERATION_OFF"
                                for e in pipeline.device_events())), \
        "the simulator's event never arrived"


def test_an_unknown_event_type_is_rejected_over_the_broker(wired):
    import json

    import paho.mqtt.publish as publish

    pipeline, consumer, runner = wired
    publish.single(config.EVENTS_TOPIC.format(truck_id="T102"),
                   json.dumps({"truckId": "T102", "type": "NOT_A_TYPE"}),
                   hostname=config.MQTT_HOST, port=config.MQTT_PORT)
    assert wait_for(lambda: any(r["reason"] == "unknown_event_type"
                                for r in pipeline.rejected))
