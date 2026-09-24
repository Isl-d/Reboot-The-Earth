"""The live fleet model: cargo temperature, risk projection, reroutes.

These are the behaviours that make the demo read correctly on stage, so they
are pinned here rather than left to the end-to-end test.
"""
import pytest

from backend import config
from backend.detector import FAILURE
from backend.state import FleetState


@pytest.fixture
def fleet():
    return FleetState()


@pytest.fixture
def truck(fleet):
    return fleet.trucks[config.REAL_TRUCK]


def feed(truck, air_c, seconds, t0=1000.0, step=2.0, door=False):
    """Telemetry at the real 2-second interval. Returns the last timestamp."""
    t = t0
    for _ in range(int(seconds / step)):
        t += step
        truck.detector.update(t, air_c, door)
        truck.apply({"ts": t, "air_c": air_c, "hum_pct": 60, "door_open": door,
                     "src": "esp8266"})
    return t


# ------------------------------------------------------------ the fleet
def test_the_fleet_is_twelve_trucks_with_one_real_sensor(fleet):
    assert len(fleet.trucks) == 12
    live = [t for t in fleet.trucks.values() if t.is_live_sensor]
    assert [t.truck_id for t in live] == [config.REAL_TRUCK]


def test_every_shipment_starts_green_and_accepted(fleet):
    for truck in fleet.trucks.values():
        feed(truck, truck.product.ideal_temp_c + 0.5, 10)
        assert truck.risk == "green", truck.truck_id
        assert not truck.as_dict()["at_risk"], truck.truck_id


def test_the_demo_shipment_starts_with_eight_days(truck):
    assert truck.life_left_h / 24 == pytest.approx(8.0)


# ------------------------------------------------- cargo lags the sensor
def test_the_cargo_warms_more_slowly_than_the_air(truck):
    feed(truck, 2.5, 20)
    feed(truck, 28.0, 60, t0=1020.0)
    assert truck.air_c == 28.0
    assert truck.product_c is not None
    assert truck.product_c < truck.air_c - 5, "a pallet cannot follow a 2 s air spike"
    assert truck.product_c > 2.5, "but it does warm up"


def test_the_shelf_life_clock_follows_the_cargo_not_the_air(truck):
    feed(truck, 2.5, 20)
    before = truck.life_left_h
    feed(truck, 28.0, 10, t0=1020.0)
    burned = before - truck.life_left_h
    # At the air temperature this would be roughly ten times worse.
    assert 0 < burned < 3.0


def test_a_lifted_lid_does_not_turn_the_fleet_amber(truck):
    """CLAUDE.md section 8, 0:40: the judges must see nothing happen."""
    feed(truck, 2.5, 30)
    t = feed(truck, 11.0, 6, t0=1030.0)
    feed(truck, 2.5, 20, t0=t)
    assert truck.risk == "green"
    assert not truck.detector.has(FAILURE)


def test_a_confirmed_failure_turns_it_amber_at_once(truck):
    feed(truck, 2.5, 20)
    t = 1020.0
    for air in (6, 10, 15, 20, 24, 27):
        t = feed(truck, air, 4, t0=t)
    feed(truck, 28.0, 40, t0=t)
    assert truck.detector.has(FAILURE)
    assert truck.risk in ("amber", "red")
    assert truck.as_dict()["at_risk"]


def test_the_risk_projection_is_the_worst_case_only_during_a_failure(truck):
    """Outside a failure, a warm spell is assumed to be fixed within the hour."""
    feed(truck, 2.5, 20)
    feed(truck, 9.0, 10, t0=1020.0)         # above the limit, not yet confirmed
    tolerant = truck.life_on_arrival_h
    truck.detector._start(FAILURE, 1040.0, 9.0, alert=True)
    assert truck.life_on_arrival_h < tolerant


# ---------------------------------------------------- approved reroutes
def test_a_reroute_shortens_the_trip_and_changes_the_destination(truck):
    feed(truck, 2.5, 20)
    before = truck.remaining_trip_h
    truck.override_destination = "store_wakrah"
    truck.status = "rerouted"
    assert truck.remaining_trip_h < before
    assert "Wakrah" in truck.destination_name


def test_a_sold_or_donated_load_stops_ageing(truck):
    feed(truck, 2.5, 20)
    truck.status = "sold"
    frozen = truck.life_left_h
    feed(truck, 30.0, 40, t0=1020.0)
    assert truck.life_left_h == frozen
    assert truck.remaining_trip_h == 0.0


def test_a_held_load_stops_moving_but_keeps_ageing(truck):
    feed(truck, 2.5, 20)
    truck.status = "held"
    where = (truck.lat, truck.lon)
    feed(truck, 20.0, 40, t0=1020.0)
    assert (truck.lat, truck.lon) == where
    assert truck.life_left_h < truck.product.life_at_ideal_h * config.START_LIFE_FRACTION


# ------------------------------------------------------- sensor faults
def test_a_broken_sensor_pauses_the_freshness_clock(truck):
    feed(truck, 2.5, 20)
    held = truck.life_left_h
    feed(truck, config.SENSOR_SENTINEL_C, 20, t0=1020.0)
    assert not truck.detector.sensor_ok
    assert truck.life_left_h == held
    assert truck.risk == "unknown"


# --------------------------------------------------------------- totals
def test_reset_puts_every_truck_back(fleet, truck):
    feed(truck, 30.0, 40)
    fleet.reset()
    assert truck.life_left_h / 24 == pytest.approx(8.0)
    assert truck.status == "rolling"
    assert truck.air_c is None and truck.product_c is None
    assert fleet.totals()["kg_at_risk"] == 0


def test_totals_add_up(fleet):
    totals = fleet.totals()
    assert totals["trucks"] == 12
    assert totals["kg_monitored"] == sum(round(t.qty_kg) for t in fleet.trucks.values())
    assert totals["audit_ok"]
