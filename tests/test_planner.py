"""Options A-D and their scoring (CLAUDE.md section 7.4)."""
import time

import pytest

from backend import config, geo, planner
from backend.freshness import get_product

LETTUCE = get_product("lettuce")


def plan_at(product_c, life_days=8.0, frac=0.12, product=LETTUCE, qty=2000,
            sensor_ok=True):
    return planner.build_plan(
        truck_id="TRK-07", product=product, qty_kg=qty, product_c=product_c,
        air_c=product_c, life_left_h=life_days * 24,
        route=geo.load_routes()["R1"], frac=frac, now=time.time(), sensor_ok=sensor_ok)


def option(plan, key):
    return next(o for o in plan.options if o.key == key)


def test_every_option_is_offered():
    assert [o.key for o in plan_at(2.0).options] == ["A", "B", "C", "D", "E", "F"]


def test_every_dispatcher_verb_has_an_option():
    """Sell, donate, hold and reroute must each be one press away."""
    verbs = plan_at(22.8, life_days=7.33).verbs
    assert set(verbs) == {"continue", "reroute", "sell", "donate", "hold"}
    assert verbs["reroute"] == ["B", "C"]


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


def test_donating_recovers_less_than_selling():
    plan = plan_at(22.8, life_days=7.33)
    assert option(plan, "E").score < option(plan, "D").score


def test_food_below_the_store_minimum_is_still_offered_to_the_food_bank():
    """Below the store's bar but safe to eat: donating rescues the whole load."""
    e = option(plan_at(30.0, life_days=1.25), "E")
    assert e.action == "donate"
    assert not e.feasible                     # no store would take it
    assert e.kg_saved > 0                     # people still would


def test_genuinely_spoiled_food_is_never_claimed_as_rescued():
    plan = plan_at(35.0, life_days=0.4)
    assert all(o.kg_saved == 0 for o in plan.options)
    assert plan.needs_human_review


def test_holding_does_not_rescue_a_load_that_is_already_out_of_specification():
    """Hold only delays the loss, so it must not claim the kilos as saved."""
    plan = plan_at(30.0, life_days=1.25)
    hold, sell = option(plan, "F"), option(plan, "D")
    assert not hold.feasible
    assert hold.kg_saved == 0
    assert sell.kg_saved > 0
    assert sell.score > hold.score


def test_holding_is_worth_something_while_the_load_is_still_in_specification():
    hold = option(plan_at(22.8, life_days=7.33), "F")
    assert hold.feasible and hold.kg_saved > 0
    assert hold.markdown_loss_qar > 0, "a missed delivery slot has to cost something"


# ------------------------------------------------------------- escalation
def test_a_clear_case_is_not_escalated():
    plan = plan_at(22.8, life_days=7.33)
    assert not plan.needs_human_review
    assert plan.recommended == "C"


def test_an_untrusted_sensor_is_always_escalated():
    plan = plan_at(22.8, life_days=7.33, sensor_ok=False)
    assert plan.needs_human_review
    assert any("trusted" in r for r in plan.review_reasons)


def test_a_load_no_option_can_save_is_escalated():
    plan = plan_at(30.0, life_days=1.25)
    assert plan.needs_human_review
    assert not any(o.feasible for o in plan.options)
    assert any("judgement" in r for r in plan.review_reasons)


def test_a_large_irreversible_action_is_escalated():
    plan = plan_at(30.0, life_days=1.25)
    assert plan.best.action in ("sell", "donate")
    assert any("irreversible" in r for r in plan.review_reasons)


def test_two_ways_to_reroute_are_one_decision_not_a_close_call():
    """B and C are always worth about the same; that is not a dilemma."""
    plan = plan_at(22.8, life_days=7.33)
    b, c = option(plan, "B"), option(plan, "C")
    assert abs(b.score - c.score) < config.REVIEW_MARGIN_QAR
    assert not plan.needs_human_review


def test_a_healthy_shipment_is_never_escalated():
    plan = plan_at(2.5)
    assert plan.recommended == "A" and not plan.needs_human_review


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
                "recommended", "recommended_verb", "needs_human_review",
                "review_reasons", "life_on_arrival_days", "kg_saved", "value_qar",
                "co2e_saved_kg", "alternatives"):
        assert key in facts
    assert len(facts["alternatives"]) == 5


def test_chicken_has_a_tighter_limit_than_lettuce():
    chicken = get_product("chicken")
    assert chicken.alert_limit_c < LETTUCE.alert_limit_c
    plan = plan_at(12.0, life_days=chicken.life_at_ideal_days * 0.8,
                   product=chicken, qty=3000)
    assert plan.recommended != "A"
