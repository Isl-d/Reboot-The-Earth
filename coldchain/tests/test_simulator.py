"""The scenario engine: does each fault actually look like that fault?"""
from __future__ import annotations

from coldchain.ingestion.pipeline import Pipeline
from coldchain.simulator import scenarios
from coldchain.simulator.runner import SimulationRunner, direct_sink


def run(scenario: str, ticks: int = 60, dt: float = 5.0) -> list[dict]:
    fleet = scenarios.build_fleet(seed=7)
    truck = fleet["T102"]
    truck.set_scenario(scenario)
    return [truck.step(dt) for _ in range(ticks)]


def temps(rows: list[dict]) -> list[float]:
    return [r["temperatureC"] for r in rows]


def test_the_payload_matches_the_documented_schema():
    row = run(scenarios.NORMAL, ticks=1)[0]
    assert set(row) == {"deviceId", "truckId", "timestamp", "temperatureC",
                        "humidityPct", "latitude", "longitude", "speedKmh",
                        "gForce", "doorOpen", "refrigerationOn"}
    assert row["deviceId"] == "TRUCK-T102"
    assert row["truckId"] == "T102"
    assert row["timestamp"].endswith("Z")


def test_normal_transport_stays_in_the_safe_band():
    # T102 carries chicken: 0-4 C.
    settled = temps(run(scenarios.NORMAL, ticks=40))[10:]
    assert max(settled) <= 4.0
    assert min(settled) >= 0.0


def test_a_temperature_excursion_crosses_the_limit_and_stays_there():
    t = temps(run(scenarios.TEMPERATURE_EXCURSION, ticks=80))
    assert t[0] <= 4.0                      # starts in spec
    assert t[-1] > 4.0                      # ends out of spec
    assert t[-1] > t[0]


def test_refrigeration_failure_warms_faster_than_an_excursion():
    fail = temps(run(scenarios.REFRIGERATION_FAILURE, ticks=30))
    creep = temps(run(scenarios.TEMPERATURE_EXCURSION, ticks=30))
    assert fail[-1] > creep[-1]


def test_refrigeration_failure_reports_the_unit_as_off():
    rows = run(scenarios.REFRIGERATION_FAILURE, ticks=5)
    assert all(r["refrigerationOn"] is False for r in rows)


def test_door_left_open_reports_the_door_and_raises_humidity():
    rows = run(scenarios.DOOR_LEFT_OPEN, ticks=30)
    assert all(r["doorOpen"] is True for r in rows)
    assert rows[-1]["humidityPct"] > rows[0]["humidityPct"]
    assert temps(rows)[-1] > temps(rows)[0]


def test_traffic_delay_slows_the_truck_without_warming_it():
    rows = run(scenarios.TRAFFIC_DELAY, ticks=40)
    assert rows[-1]["speedKmh"] < 15.0
    assert max(temps(rows)[10:]) <= 4.5     # cooling still works


def test_combined_failure_is_both_problems_at_once():
    rows = run(scenarios.COMBINED_FAILURE, ticks=40)
    assert rows[-1]["speedKmh"] < 15.0
    assert rows[-1]["refrigerationOn"] is False
    assert temps(rows)[-1] > 10.0


def test_the_truck_moves_along_its_route():
    rows = run(scenarios.NORMAL, ticks=40)
    assert (rows[0]["latitude"], rows[0]["longitude"]) != \
           (rows[-1]["latitude"], rows[-1]["longitude"])


def test_an_unknown_scenario_is_refused():
    fleet = scenarios.build_fleet()
    try:
        fleet["T102"].set_scenario("NOT_A_SCENARIO")
    except ValueError as exc:
        assert "NOT_A_SCENARIO" in str(exc)
    else:
        raise AssertionError("an unknown scenario should not be accepted")


def test_the_same_seed_gives_the_same_run():
    a = temps([scenarios.build_fleet(seed=7)["T102"].step(5.0) for _ in range(1)])
    fleet_b = scenarios.build_fleet(seed=7)
    b = [fleet_b["T102"].step(5.0)["temperatureC"]]
    assert a == b


def test_the_runner_feeds_the_pipeline_end_to_end():
    pipeline = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(pipeline), tick_s=5.0)
    runner.set_scenario("T102", scenarios.REFRIGERATION_FAILURE)
    for _ in range(30):
        runner.tick()

    state = next(t for t in pipeline.fleet_states() if t.truck_id == "T102")
    assert state.temperature_c > 4.0
    assert state.refrigeration_on is False
    assert not pipeline.rejected            # the simulator emits only valid data
    assert [i for i in pipeline.all_incidents()
            if i.type == "REFRIGERATION_FAILURE"]


def test_every_simulated_reading_survives_validation():
    pipeline = Pipeline(persist=False)
    runner = SimulationRunner(sink=direct_sink(pipeline), tick_s=5.0)
    for name in scenarios.ALL:
        for tid in runner.trucks:
            runner.set_scenario(tid, name)
        for _ in range(20):
            runner.tick()
    assert pipeline.rejected == []


def test_setting_a_scenario_does_not_reset_the_speed_multiplier():
    """Found on a live run: a x10 demo silently dropped back to x1.

    The scenario request carries no speed of its own unless the caller gives
    one, so setting a fault must leave an accelerated run accelerated.
    """
    from coldchain.schemas import ScenarioRequest

    runner = SimulationRunner(sink=lambda *_: None, tick_s=2.0)
    runner.start(10.0)
    runner.stop()
    assert runner.speed_multiplier == 10.0

    req = ScenarioRequest(truckId="T102", scenario="REFRIGERATION_FAILURE")
    assert req.speed_multiplier is None
    runner.set_scenario(req.truck_id, req.scenario, req.speed_multiplier)
    assert runner.speed_multiplier == 10.0

    # An explicit multiplier still applies.
    runner.set_scenario("T102", "NORMAL", 3.0)
    assert runner.speed_multiplier == 3.0
