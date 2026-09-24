"""MQTT ingest: the only way telemetry enters ColdGuard.

Subscribes to `coldguard/+/telemetry`, validates, enriches the NodeMCU's
minimal payload, runs the detector and the freshness model, and hands a
confirmed cooling failure to the planner and the agent.

Everything here runs on paho's network thread. Slow work (the local LLM) is
pushed onto a worker thread so telemetry never stalls behind it.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from . import agent, config, planner
from .db import db
from .detector import FAILURE
from .state import FleetState

log = logging.getLogger("coldguard.ingest")


def _clean_reading(truck_id: str, payload: dict[str, Any], now: float) -> dict[str, Any]:
    """Normalise both payload shapes into one reading (CLAUDE.md section 6)."""
    out: dict[str, Any] = {"truck_id": truck_id}
    air = payload.get("air_c")
    out["air_c"] = float(air) if isinstance(air, (int, float)) else None
    hum = payload.get("hum_pct")
    out["hum_pct"] = float(hum) if isinstance(hum, (int, float)) else None
    out["door_open"] = bool(payload.get("door_open", False))
    for key in ("lat", "lon"):
        v = payload.get(key)
        out[key] = float(v) if isinstance(v, (int, float)) else None
    # The board has no clock, so the backend stamps arrival time. The simulator
    # sends its own `ts`, but receive time keeps every truck on one timeline.
    out["ts"] = now
    out["src"] = payload.get("src") or ("sim" if payload.get("lat") is not None else "esp8266")
    return out


class Ingest:
    """Owns the MQTT client and the decision pipeline."""

    def __init__(self, state: FleetState, clock=time.time) -> None:
        self.state = state
        self.clock = clock          # swappable so tests can replay a timeline
        self.client = None
        self._stop = threading.Event()
        self._watchdog: threading.Thread | None = None

    # --------------------------------------------------------------- MQTT
    def start(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:                       # pragma: no cover
            log.error("paho-mqtt is not installed; no telemetry will arrive")
            return
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id="coldguard-backend")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        try:
            self.client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
            self.client.loop_start()
            log.info("MQTT connecting to %s:%s", config.MQTT_HOST, config.MQTT_PORT)
        except Exception as exc:                  # pragma: no cover - demo safety
            log.warning("MQTT unavailable (%s); the dashboard still runs", exc)
        self._watchdog = threading.Thread(target=self._watch, name="coldguard-watchdog",
                                          daemon=True)
        self._watchdog.start()

    def stop(self) -> None:
        self._stop.set()
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client, _userdata, _flags, reason_code, _props=None) -> None:
        log.info("MQTT connected (%s), subscribing to %s", reason_code, config.TELEMETRY_TOPIC)
        client.subscribe(config.TELEMETRY_TOPIC, qos=0)

    def publish_control(self, truck_id: str, message: dict[str, Any]) -> bool:
        """Send a command to the simulator (demo panel only)."""
        if self.client is None:
            return False
        topic = config.CONTROL_TOPIC.format(truck_id=truck_id)
        self.client.publish(topic, json.dumps(message))
        log.info("control -> %s %s", topic, message)
        return True

    # ------------------------------------------------------------ pipeline
    def _on_message(self, _client, _userdata, msg) -> None:
        try:
            payload = json.loads(msg.payload or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        parts = msg.topic.split("/")
        truck_id = payload.get("truck_id") or (parts[1] if len(parts) > 2 else None)
        if not truck_id:
            return
        self.handle(truck_id, payload)

    def handle(self, truck_id: str, payload: dict[str, Any]) -> None:
        """One telemetry message, start to finish. Also used by the tests."""
        state = self.state
        truck = state.trucks.get(truck_id)
        if truck is None:
            return
        reading = _clean_reading(truck_id, payload, self.clock())

        with state.lock:
            events = truck.detector.update(reading["ts"], reading["air_c"],
                                           reading["door_open"])
            truck.apply(reading)
            snapshot = truck.as_dict()

        db.insert_reading(reading)
        state.bus.publish("reading", snapshot)
        for ev in events:
            self._record_event(truck_id, ev)

    def _record_event(self, truck_id: str, ev) -> None:
        state = self.state
        payload = ev.as_dict()
        with state.lock:
            state.events.appendleft(payload)
        db.insert_event(payload)
        state.bus.publish("event", payload)
        if ev.type == FAILURE and ev.alert and ev.ended_at is None:
            threading.Thread(target=self._plan_for, args=(truck_id,),
                             name=f"coldguard-plan-{truck_id}", daemon=True).start()

    def _plan_for(self, truck_id: str) -> None:
        """Build options, ask the local model for words, wait for a human."""
        state = self.state
        with state.lock:
            truck = state.trucks.get(truck_id)
            if truck is None or truck.decision_id is not None:
                return                              # one open decision per truck
            plan = planner.build_plan(
                truck_id=truck_id, product=truck.product, qty_kg=truck.qty_kg,
                product_c=truck.product_c if truck.product_c is not None else truck.product.ideal_temp_c,
                air_c=truck.air_c if isinstance(truck.air_c, (int, float)) else None,
                life_left_h=truck.life_left_h, route=truck.route, frac=truck.frac,
                now=self.clock(), sensor_ok=truck.detector.sensor_ok)
            decision_id = state.next_decision_id()
            truck.decision_id = decision_id

        facts = plan.facts()
        state.bus.publish("alert", {"truck_id": truck_id, "decision_id": decision_id,
                                    "recommended": plan.recommended,
                                    "needs_human_review": plan.needs_human_review,
                                    "product": plan.product, "air_c": plan.air_c})
        text = agent.explain(facts)                 # up to 5 s, then the template

        with state.lock:
            record = {
                "decision_id": decision_id,
                "truck_id": truck_id,
                "product": plan.product,
                "qty_kg": plan.qty_kg,
                "created_at": plan.generated_at,
                "options": [o.as_dict() for o in plan.options],
                "recommended": plan.recommended,
                "needs_human_review": plan.needs_human_review,
                "review_reasons": plan.review_reasons,
                "verbs": plan.verbs,
                "chosen": None,
                "chosen_option": plan.best.as_dict(),
                "facts": facts,
                "text_en": text["en"],
                "text_ar": text["ar"],
                "text_source": text["source"],
                "text_note": text.get("note", ""),
                "approved_by": None,
                "approved_at": None,
            }
            rec = state.audit.append("decision", {
                "decision_id": decision_id, "truck_id": truck_id,
                "recommended": plan.recommended, "facts": facts,
                "options": [o.as_dict() for o in plan.options]})
            record["prev_hash"], record["hash"] = rec.prev_hash, rec.hash
            state.decisions[decision_id] = record

        db.insert_decision(record)
        state.bus.publish("decision", record)
        log.info("decision %s for %s: %s%s (%s)", decision_id, truck_id,
                 plan.recommended,
                 " - escalated for human review" if plan.needs_human_review else "",
                 text["source"])

    # ------------------------------------------------------------ watchdog
    def _watch(self) -> None:
        """A truck that stops reporting has a sensor fault too (section 7.2)."""
        while not self._stop.wait(2.0):
            now = self.clock()
            with self.state.lock:
                trucks = list(self.state.trucks.values())
            for truck in trucks:
                for ev in truck.detector.check_timeout(now):
                    self._record_event(truck.truck_id, ev)
