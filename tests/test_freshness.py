"""The Q10 shelf-life model (CLAUDE.md section 7.3)."""
import pytest

from backend import config, freshness as fr


@pytest.fixture
def lettuce():
    return fr.get_product("lettuce")


def test_products_load_from_csv():
    products = fr.load_products()
    assert {"lettuce", "chicken", "milk"} <= set(products)
    assert products["chicken"].alert_limit_c == 4.0


def test_speed_is_one_at_the_ideal_temperature(lettuce):
    assert fr.aging_speed(lettuce.ideal_temp_c, lettuce) == pytest.approx(1.0)


def test_ten_degrees_warmer_is_q10_times_faster(lettuce):
    assert fr.aging_speed(lettuce.ideal_temp_c + 10, lettuce) == pytest.approx(lettuce.q10)
    assert fr.aging_speed(lettuce.ideal_temp_c + 20, lettuce) == pytest.approx(lettuce.q10 ** 2)


def test_colder_than_ideal_ages_more_slowly(lettuce):
    assert fr.aging_speed(0.0, lettuce) < 1.0


def test_advance_consumes_the_demo_clock(lettuce):
    left = fr.advance(100.0, 1.0, lettuce.ideal_temp_c, lettuce, demo_speed=120)
    assert 100.0 - left == pytest.approx(120 / 3600, rel=1e-6)


def test_advance_never_goes_negative(lettuce):
    assert fr.advance(0.5, 3600.0, 40.0, lettuce) == 0.0


def test_life_on_arrival_matches_the_brief(lettuce):
    # Section 7.3: plain subtraction when the load is cooling normally.
    assert fr.life_on_arrival_h(192.0, 24.0) == pytest.approx(168.0)
    # Section 7.4: warm cargo burns the remaining trip faster.
    assert fr.life_on_arrival_h(192.0, 24.0, speed_on_the_way=3.0) == pytest.approx(120.0)


def test_risk_bands(lettuce):
    minimum = lettuce.min_life_on_arrival_h            # 144 h
    assert fr.risk_level(minimum + 1, lettuce) == "green"
    assert fr.risk_level(minimum - 1, lettuce) == "amber"
    assert fr.risk_level(1.0, lettuce) == "red"
    assert fr.risk_level(-5.0, lettuce) == "red"


def test_at_risk_is_the_store_minimum(lettuce):
    assert fr.at_risk(lettuce.min_life_on_arrival_h - 0.1, lettuce)
    assert not fr.at_risk(lettuce.min_life_on_arrival_h, lettuce)


def test_demo_scenario_starts_green(lettuce):
    """Section 8: 8 days of life, 1 day of trip, the store needs 6."""
    life = lettuce.life_at_ideal_h * config.START_LIFE_FRACTION
    assert life == pytest.approx(8 * 24)
    on_arrival = fr.life_on_arrival_h(life, 24.0)
    assert on_arrival / 24 == pytest.approx(7.0)
    assert fr.risk_level(on_arrival, lettuce) == "green"
