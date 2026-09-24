"""The agent writes words, never numbers (CLAUDE.md sections 3 and 7.5)."""
import time

import pytest

from backend import agent, geo, planner
from backend.freshness import get_product


@pytest.fixture
def facts():
    plan = planner.build_plan(
        truck_id="TRK-07", product=get_product("lettuce"), qty_kg=2000,
        product_c=22.8, air_c=28.0, life_left_h=7.33 * 24,
        route=geo.load_routes()["R1"], frac=0.12, now=time.time())
    return plan.facts()


def test_the_template_is_grounded_in_both_languages(facts):
    text = agent.template(facts)
    for language in ("en", "ar"):
        ok, bad = agent.check_numbers(text[language], facts)
        assert ok, f"{language} invented {bad}"


def test_the_template_says_something_in_arabic(facts):
    ar = agent.template(facts)["ar"]
    assert any("؀" <= ch <= "ۿ" for ch in ar)


def test_invented_numbers_are_caught(facts):
    ok, bad = agent.check_numbers("It will spoil in 42 hours and lose 99 kg.", facts)
    assert not ok and set(bad) == {"42", "99"}


def test_arabic_digits_are_caught(facts):
    ok, bad = agent.check_numbers("سيتلف خلال ٤٢ ساعة", facts)
    assert not ok and bad == ["42"]


def test_thousands_separators_are_accepted(facts):
    ok, _ = agent.check_numbers(f"It saves {facts['kg_saved']:,} kg.", facts)
    assert ok


def test_numbers_inside_names_are_not_numbers(facts):
    ok, bad = agent.check_numbers("qwen2.5 on route R1 cut CO2e emissions.", facts)
    assert ok, bad


def test_explain_falls_back_to_the_template_without_ollama(facts, monkeypatch):
    monkeypatch.setattr(agent, "_ask_ollama", lambda _facts: None)
    out = agent.explain(facts)
    assert out["source"] == "template"
    assert out["grounded"] and out["en"] and out["ar"]


def test_a_hallucinating_model_is_rejected(facts, monkeypatch):
    monkeypatch.setattr(agent, "_ask_ollama",
                        lambda _facts: {"en": "Throw away 777 kg now.", "ar": "تخلص من ٧٧٧ كجم"})
    out = agent.explain(facts)
    assert out["source"] == "template"
    assert "777" in out["note"]


def test_a_grounded_model_answer_is_kept(facts, monkeypatch):
    good = {"en": f"Send {facts['truck_id']} to {facts['destination']} now. "
                  f"It keeps {facts['kg_saved']} kg.",
            "ar": f"أرسل {facts['truck_id']} إلى {facts['destination']}. "
                  f"ينقذ {facts['kg_saved']} كجم."}
    monkeypatch.setattr(agent, "_ask_ollama", lambda _facts: good)
    out = agent.explain(facts)
    assert out["source"].startswith("qwen")
    assert out["en"] == good["en"]


def test_a_broken_ollama_never_breaks_the_demo(facts, monkeypatch):
    """Whatever the local model does, a decision still gets its two sentences."""
    import httpx

    def explode(*_a, **_kw):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", explode)
    out = agent.explain(facts)
    assert out["source"] == "template"
    assert agent.check_numbers(out["en"], facts)[0]


def test_a_slow_model_falls_back_too(facts, monkeypatch):
    import httpx

    def timeout(*_a, **_kw):
        raise httpx.ReadTimeout("too slow")

    monkeypatch.setattr(httpx, "post", timeout)
    assert agent.explain(facts)["source"] == "template"


# ------------------------------------------------- escalation to a human
@pytest.fixture
def review_facts():
    plan = planner.build_plan(
        truck_id="TRK-07", product=get_product("lettuce"), qty_kg=2000,
        product_c=30.0, air_c=32.0, life_left_h=30.0,
        route=geo.load_routes()["R1"], frac=0.25, now=time.time())
    assert plan.needs_human_review
    return plan.facts()


def test_the_review_text_offers_the_four_verbs(review_facts):
    text = agent.template(review_facts)
    for verb in ("sell", "donate", "hold", "reroute"):
        assert verb in text["en"].lower()
    assert "قرار بشري" in text["ar"]


def test_the_review_text_recommends_nothing(review_facts):
    en = agent.template(review_facts)["en"].lower()
    assert "recommend" not in en
    assert "needs a person to decide" in en


def test_the_review_text_is_grounded_too(review_facts):
    text = agent.template(review_facts)
    for language in ("en", "ar"):
        ok, bad = agent.check_numbers(text[language], review_facts)
        assert ok, f"{language} invented {bad}"
