"""Options A-D and their scoring (CLAUDE.md section 7.4)."""
import time

import pytest

from backend import config, geo, planner
from backend.freshness import get_product

LETTUCE = get_product("lettuce")


def plan_at(product_c, life_days=8.0, frac=0.12, product=LETTUCE, qty=2000):
    return planner.build_plan(
        truck_id="TRK-07", product=product, qty_kg=qty, product_c=product_c,
        air_c=product_c, life_left_h=life_days * 24,
        route=geo.load_routes()["R1"], frac=frac, now=time.time())


def option(plan, key):
    return next(o for o in plan.options if o.key == key)


def test_every_option_is_offered():
    assert [o.key for o in plan_at(2.0).options] == ["A", "B", "C", "D"]


def test_a_healthy_shipment_is_left_alone():
    """Never reroute a truck that is going to be accepted anyway."""
    plan = plan_at(2.5)
    assert plan.recommended == "A"
    assert option(plan, "A").feasible


def test_the_demo_scenario_recommends_delivering_direct(): 
    """Section 8: warm TRK-07 must be sent straight to the nearest store."""
    plan = plan_at(22.8, life_days=7.33)
    assert plan.recommended == "C"
    c = option(plan, "C")
    assert c.feasible
    assert c.life_on_arrival_days >= LETTUCE.min_life_on_arrival_days


def test_continuing_as_planned_fails_once_the_cargo_is_warm():
    a = option(plan_at(22.8, life_days=7.33), "A")
    assert not a.feasible
    assert a.kg_saved == 0


def test_the_recommendation_holds_across_the_whole_demo_window():
    """From the alert to well after the scripted approval, C must stay right."""
    for product_c, life_days in ((14.7, 7.79), (18.5, 7.64), (22.8, 7.33), (24.5, 6.87)):
        plan = plan_at(product_c, life_days=life_days)
        assert plan.recommended == "C", f"at {product_c} C"
        assert option(plan, "C").life_on_arrival_days >= LETTUCE.min_life_on_arrival_days


def test_selling_now_is_always_possible_but_worth_less():
    plan = plan_at(22.8, life_days=7.33)
    c, d = option(plan, "C"), option(plan, "D")
    assert d.markdown_loss_qar > 0
    assert d.score < c.score
    assert d.kg_saved == pytest.approx(2000)


def test_a_spoiled_load_is_offered_to_the_food_bank():
    plan = plan_at(35.0, life_days=0.4)
    d = option(plan, "D")
    assert "donate" in d.title_en.lower() or "food bank" in d.destination_name.lower()


def test_score_is_value_minus_distance_minus_markdown():
    c = option(plan_at(22.8, life_days=7.33), "C")
    expected = (c.kg_saved * LETTUCE.value_qar_per_kg
                - c.extra_km * config.COST_PER_KM_QAR - c.markdown_loss_qar)
    assert c.score == pytest.approx(round(expected), abs=1)


def test_warm_cargo_burns_the_remaining_trip_faster():
    warm, cold = option(plan_at(25.0), "A"), option(plan_at(2.0), "A")
    assert warm.life_on_arrival_h < cold.life_on_arrival_h


def test_facts_carry_only_computed_numbers():
    facts = plan_at(22.8, life_days=7.33).facts()
    for key in ("truck_id", "product", "qty_kg", "air_c", "product_c", "aging_speed_x",
                "life_left_days", "store_minimum_days", "if_nothing_done_days",
                "recommended", "life_on_arrival_days", "kg_saved", "value_qar",
                "co2e_saved_kg", "alternatives"):
        assert key in facts
    assert len(facts["alternatives"]) == 3


def test_chicken_has_a_tighter_limit_than_lettuce():
    chicken = get_product("chicken")
    assert chicken.alert_limit_c < LETTUCE.alert_limit_c
    plan = plan_at(12.0, life_days=chicken.life_at_ideal_days * 0.8,
                   product=chicken, qty=3000)
    assert plan.recommended != "A"
