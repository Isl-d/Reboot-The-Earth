"""The explanation agent (CLAUDE.md section 7.5).

Hard rule of this project: **the LLM never produces numbers.** Every figure is
computed by planner.py and handed over as JSON; the model only turns that JSON
into two sentences of Arabic and two of English.

Three things keep that promise honest:

1. The prompt forbids arithmetic and new numbers.
2. `check_numbers()` re-reads the generated text and rejects it if it contains a
   number that is not in the facts (Arabic-Indic digits included).
3. If the model is slow, missing or ungrounded, a fixed template writes the same
   sentences from the same JSON. The demo never depends on the LLM.
"""
from __future__ import annotations

import json
import re
from typing import Any

from . import config

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")
# A standalone number: not glued to a letter, so "CO2e", "qwen2.5" and "R1" are
# names, not figures the model invented.
_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")

SYSTEM = """You are a cold-chain dispatcher's assistant.
You will be given a JSON object of facts that were computed by a separate system.
Write exactly two sentences in English and exactly two sentences in Arabic for a
logistics manager.

Rules:
- Use ONLY numbers that appear in the JSON. Never calculate, round or invent a number.
- Do not add numbers of your own, not even dates, times or percentages.
- If "needs_human_review" is true, do NOT recommend anything. Say what is wrong
  and that the manager must choose between selling, donating, holding and
  rerouting. Otherwise, explain the recommended action.
- Be concrete and calm. No emoji, no bullet points, no headings.
- Reply with JSON only, in this exact shape: {"en": "...", "ar": "..."}
"""


def _numbers_in(text: str) -> list[str]:
    plain = _THOUSANDS.sub("", str(text).translate(_AR_DIGITS))
    return _NUM.findall(plain)


def _allowed_numbers(facts: dict[str, Any]) -> set[str]:
    """Every number the model is allowed to write, in several harmless forms."""
    allowed: set[str] = set()

    def add(v: Any) -> None:
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            for form in (f"{v:g}", f"{v:.0f}", f"{v:.1f}", str(abs(v)), f"{abs(v):.0f}"):
                allowed.add(form.lstrip("+"))
        elif isinstance(v, str):
            allowed.update(_numbers_in(v))
        elif isinstance(v, dict):
            for x in v.values():
                add(x)
        elif isinstance(v, list):
            for x in v:
                add(x)

    add(facts)
    return allowed


def check_numbers(text: str, facts: dict[str, Any]) -> tuple[bool, list[str]]:
    """(ok, offending numbers). Used to reject hallucinated figures."""
    allowed = _allowed_numbers(facts)
    bad = [n for n in _numbers_in(text)
           if n.lstrip("-") not in allowed and n not in allowed]
    return (not bad), bad


def template(facts: dict[str, Any]) -> dict[str, str]:
    """Deterministic fallback with exactly the same numbers. Always available."""
    f = facts
    if f.get("needs_human_review"):
        return _review_template(f)
    en = (
        f"{f['truck_id']} is running at {f['air_c']} °C and its cargo has reached "
        f"{f['product_c']} °C, so its {f['qty_kg']} kg of {f['product']} is ageing "
        f"{f['aging_speed_x']} times faster than normal and would "
        f"arrive with {f['if_nothing_done_days']} days of freshness against the "
        f"{f['store_minimum_days']} days the store accepts. "
        f"{f['recommended_action_en']} ({f['destination']}) brings freshness on arrival back to "
        f"{f['life_on_arrival_days']} days and saves {f['kg_saved']} kg, worth about "
        f"{f['value_qar']} QAR and {f['co2e_saved_kg']} kg of CO2e."
    )
    ar = (
        f"تعمل الشاحنة {f['truck_id']} عند {f['air_c']} درجة مئوية وبلغت حرارة الحمولة "
        f"{f['product_c']} درجة، لذا فإن {f['qty_kg']} كجم من "
        f"المنتج تتقادم أسرع بمقدار {f['aging_speed_x']} مرة وستصل بنضارة "
        f"{f['if_nothing_done_days']} يوم مقابل {f['store_minimum_days']} يوم يطلبها المتجر. "
        f"يوصى بـ {f['recommended_action_ar']} إلى {f['destination']}، ما يعيد النضارة عند الوصول "
        f"إلى {f['life_on_arrival_days']} يوم وينقذ {f['kg_saved']} كجم بقيمة تقارب "
        f"{f['value_qar']} ريال و{f['co2e_saved_kg']} كجم من ثاني أكسيد الكربون."
    )
    return {"en": en, "ar": ar}


def _review_template(f: dict[str, Any]) -> dict[str, str]:
    """What we say when the system will not decide on its own."""
    reason_en = " ".join(f.get("review_reasons") or []) or "The numbers do not settle it."
    en = (
        f"{f['truck_id']} needs a person to decide: its {f['qty_kg']} kg of {f['product']} "
        f"is at {f['product_c']} °C and would arrive with {f['if_nothing_done_days']} days "
        f"of freshness against the {f['store_minimum_days']} days the store accepts. "
        f"{reason_en} Choose one: sell, donate, hold or reroute."
    )
    ar = (
        f"تحتاج الشاحنة {f['truck_id']} إلى قرار بشري: حمولتها {f['qty_kg']} كجم عند "
        f"{f['product_c']} درجة مئوية وستصل بنضارة {f['if_nothing_done_days']} يوم مقابل "
        f"{f['store_minimum_days']} يوم يطلبها المتجر. "
        f"الخيارات المتاحة: البيع أو التبرع أو الاحتفاظ أو إعادة التوجيه."
    )
    return {"en": en, "ar": ar}


def _ask_ollama(facts: dict[str, Any]) -> dict[str, str] | None:
    """One call to the local model. Returns None on any problem at all."""
    try:
        import httpx
    except ImportError:
        return None
    prompt = f"{SYSTEM}\n\nFACTS:\n{json.dumps(facts, ensure_ascii=False)}\n\nJSON:"
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/generate",
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "format": "json", "options": {"temperature": 0, "seed": 7}},
            timeout=config.OLLAMA_TIMEOUT_S,
        )
        r.raise_for_status()
        raw = r.json().get("response", "")
        data = json.loads(raw)
    except Exception:
        return None
    en, ar = str(data.get("en", "")).strip(), str(data.get("ar", "")).strip()
    if not en or not ar:
        return None
    return {"en": en, "ar": ar}


def explain(facts: dict[str, Any]) -> dict[str, Any]:
    """Two sentences per language plus provenance, never raising."""
    out = _ask_ollama(facts)
    if out is not None:
        ok_en, bad_en = check_numbers(out["en"], facts)
        ok_ar, bad_ar = check_numbers(out["ar"], facts)
        if ok_en and ok_ar:
            return {**out, "source": config.OLLAMA_MODEL, "grounded": True}
        return {**template(facts), "source": "template",
                "grounded": True,
                "note": f"model output rejected: ungrounded numbers {bad_en + bad_ar}"}
    return {**template(facts), "source": "template", "grounded": True,
            "note": "local model unavailable or slow; fixed template used"}
