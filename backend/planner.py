"""Action planner (CLAUDE.md section 7.4).

For a shipment the detector has flagged, build the four options, score them
with money and kilometres, and recommend the best one. Everything is plain
arithmetic: the LLM only writes prose about the numbers this module produced.

| Option | Action  | Meaning                                                 |
| ------ | ------- | ------------------------------------------------------- |
| A      | continue| Continue as planned                                     |
| B      | reroute | Divert to the nearest cold store, then continue         |
| C      | reroute | Deliver direct to the nearest supermarket (skip the hub)|
| D      | sell    | Sell now with a markdown                                |
| E      | donate  | Donate to the food bank while it is still safe to eat   |
| F      | hold    | Park in the nearest cold room and decide later          |

A-D are the four options in the brief; E and F split donating and holding out
of D so that the four verbs a dispatcher actually uses - **sell, donate, hold,
reroute** - are each their own button.

An option is feasible when the freshness left on arrival is at least the
store's minimum. Assumption (section 7.4): the cargo keeps ageing at its
current temperature until it reaches working cooling.

    score = kg_saved * value_per_kg - extra_km * cost_per_km - markdown_loss

**When the system will not decide.** The planner escalates to a person instead
of recommending when the top two options are within REVIEW_MARGIN_QAR of each
other, when the sensor cannot be trusted, when nothing is feasible, or when the
best action is irreversible and large. The dashboard then shows the four verbs
and waits. Approval is always required either way (section 3); escalation says
the arithmetic alone does not settle it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from . import config, geo
from .freshness import Product, aging_speed, life_on_arrival_h

TITLES = {
    "A": ("Continue as planned", "المتابعة كما هو مخطط"),
    "B": ("Divert to the nearest cold store", "التحويل إلى أقرب مخزن مبرد"),
    "C": ("Deliver direct to the nearest supermarket", "التسليم مباشرة إلى أقرب سوبر ماركت"),
    "D": ("Sell now with a markdown", "البيع الآن بخصم"),
    "E": ("Donate to the food bank", "التبرع لبنك الطعام"),
    "F": ("Hold in the nearest cold room", "الاحتفاظ في أقرب غرفة تبريد"),
}
# The verb a dispatcher presses. Several options can share one verb.
ACTIONS = {"A": "continue", "B": "reroute", "C": "reroute",
           "D": "sell", "E": "donate", "F": "hold"}
ACTION_LABELS = {
    "continue": ("Continue", "المتابعة"),
    "reroute": ("Reroute", "إعادة التوجيه"),
    "sell": ("Sell", "البيع"),
    "donate": ("Donate", "التبرع"),
    "hold": ("Hold", "الاحتفاظ"),
}


@dataclass
class Option:
    key: str
    action: str
    title_en: str
    title_ar: str
    destination_id: str
    destination_name: str
    extra_km: float
    warm_drive_h: float
    remaining_trip_h: float
    life_on_arrival_h: float
    life_on_arrival_days: float
    feasible: bool
    kg_saved: float
    revenue_qar: float
    extra_cost_qar: float
    markdown_loss_qar: float
    score: float
    co2e_saved_kg: float
    why: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Plan:
    truck_id: str
    product: str
    qty_kg: float
    product_c: float
    air_c: float
    aging_speed: float
    life_left_h: float
    min_life_on_arrival_h: float
    options: list[Option]
    recommended: str
    generated_at: float
    needs_human_review: bool = False
    review_reasons: list[str] = field(default_factory=list)
    sensor_ok: bool = True
    demo_speed: float = field(default_factory=lambda: config.DEMO_SPEED)

    @property
    def best(self) -> Option:
        return next(o for o in self.options if o.key == self.recommended)

    @property
    def verbs(self) -> dict[str, list[str]]:
        """Option keys grouped by the verb a dispatcher presses."""
        out: dict[str, list[str]] = {}
        for o in self.options:
            out.setdefault(o.action, []).append(o.key)
        return out

    def as_dict(self) -> dict:
        d = asdict(self)
        d["options"] = [o.as_dict() for o in self.options]
        return d

    def facts(self) -> dict:
        """The compact JSON of facts handed to the agent. Numbers only from here."""
        best = self.best
        baseline = next(o for o in self.options if o.key == "A")
        return {
            "truck_id": self.truck_id,
            "product": self.product,
            "qty_kg": round(self.qty_kg),
            "air_c": round(self.air_c, 1),
            "product_c": round(self.product_c, 1),
            "aging_speed_x": round(self.aging_speed, 1),
            "life_left_days": round(self.life_left_h / 24.0, 1),
            "store_minimum_days": round(self.min_life_on_arrival_h / 24.0, 1),
            "if_nothing_done_days": round(baseline.life_on_arrival_days, 1),
            "recommended": best.key,
            "recommended_verb": best.action,
            "recommended_action_en": best.title_en,
            "recommended_action_ar": best.title_ar,
            "needs_human_review": self.needs_human_review,
            "review_reasons": self.review_reasons,
            "destination": best.destination_name,
            "life_on_arrival_days": round(best.life_on_arrival_days, 1),
            "kg_saved": round(best.kg_saved),
            "value_qar": round(best.revenue_qar - best.extra_cost_qar - best.markdown_loss_qar),
            "co2e_saved_kg": round(best.co2e_saved_kg),
            "alternatives": [
                {"key": o.key, "verb": o.action, "action_en": o.title_en,
                 "life_on_arrival_days": round(o.life_on_arrival_days, 1),
                 "feasible": o.feasible}
                for o in self.options if o.key != best.key
            ],
        }


def _score(kg_saved: float, value_per_kg: float, extra_km: float,
           markdown_loss: float) -> tuple[float, float, float]:
    revenue = kg_saved * value_per_kg
    cost = extra_km * config.COST_PER_KM_QAR
    return revenue, cost, revenue - cost - markdown_loss


def build_plan(*, truck_id: str, product: Product, qty_kg: float, product_c: float,
               life_left_h: float, route: geo.Route, frac: float, now: float,
               air_c: float | None = None, sensor_ok: bool = True) -> Plan:
    """Build options A-D for one at-risk shipment.

    `product_c` is the temperature of the cargo itself (what ages the food);
    `air_c` is the raw sensor reading, carried through for the human text.
    """
    places = geo.load_places()
    speed = aging_speed(product_c, product)
    lat, lon = route.point_at(frac)
    remaining_km = route.remaining_km(frac)
    dest = places.get(route.destination_id)
    dest_name = dest.name if dest else route.destination_id
    options: list[Option] = []

    def add(key: str, *, destination, extra_km: float, warm_h: float, cold_h: float,
            markdown: float, recovered_fraction: float, why: str,
            feasible_override: bool | None = None):
        """One option. `warm_h` ages at the current speed, `cold_h` at ideal speed."""
        remaining_h = warm_h + cold_h
        arrival = life_on_arrival_h(life_left_h, warm_h, speed)
        arrival = life_on_arrival_h(arrival, cold_h, 1.0)
        feasible = (arrival >= product.min_life_on_arrival_h if feasible_override is None
                    else feasible_override)
        # Full credit only when the store would accept the load. Selling at a
        # markdown or donating still rescues food that is under the store's
        # minimum, because those channels have no minimum. Holding does not:
        # it only delays the loss, so it earns nothing once the load is out of
        # specification.
        action = ACTIONS[key]
        rescued = feasible or (action in ("sell", "donate") and arrival > 0)
        kg = qty_kg * recovered_fraction if rescued else 0.0
        markdown_loss = markdown * qty_kg * product.value_qar_per_kg
        revenue, cost, score = _score(kg, product.value_qar_per_kg, extra_km, markdown_loss)
        en, ar = TITLES[key]
        options.append(Option(
            key=key, action=action, title_en=en, title_ar=ar,
            destination_id=getattr(destination, "place_id", str(destination)),
            destination_name=getattr(destination, "name", str(destination)),
            extra_km=round(extra_km, 1), warm_drive_h=round(warm_h, 2),
            remaining_trip_h=round(remaining_h, 2),
            life_on_arrival_h=round(arrival, 1),
            life_on_arrival_days=round(arrival / 24.0, 2),
            feasible=feasible, kg_saved=round(kg),
            revenue_qar=round(revenue), extra_cost_qar=round(cost),
            markdown_loss_qar=round(markdown_loss),
            score=round(score), co2e_saved_kg=round(kg * config.CO2E_PER_KG_FOOD),
            why=why))

    # A - continue as planned -------------------------------------------------
    add("A", destination=dest or route.destination_id, extra_km=0.0,
        warm_h=geo.drive_h(remaining_km) + config.HANDOVER_WAREHOUSE_H, cold_h=0.0,
        markdown=0.0, recovered_fraction=1.0,
        why=(f"{remaining_km:.0f} km left plus {config.HANDOVER_WAREHOUSE_H:.0f} h in the hub, "
             f"all of it at {product_c:.1f} °C."))

    # B - divert to the nearest cold store, cooling restored there -------------
    cold, km_to_cold = geo.nearest_place(lat, lon, ("cold_store", "warehouse"), cold_only=True)
    km_cold_to_dest = (geo.haversine_km(cold.lat, cold.lon, dest.lat, dest.lon) * config.ROAD_FACTOR
                       if dest else 0.0)
    add("B", destination=cold, extra_km=km_to_cold + km_cold_to_dest - remaining_km,
        warm_h=geo.drive_h(km_to_cold),
        cold_h=geo.drive_h(km_cold_to_dest) + config.HANDOVER_WAREHOUSE_H,
        markdown=0.0, recovered_fraction=1.0,
        why=(f"{km_to_cold:.0f} km warm to {cold.name}, then cooling is restored and the "
             f"load continues to {dest_name}."))

    # C - deliver direct to the nearest supermarket ---------------------------
    store, km_to_store = geo.nearest_place(lat, lon, ("store",))
    add("C", destination=store, extra_km=km_to_store - remaining_km,
        warm_h=geo.drive_h(km_to_store), cold_h=config.HANDOVER_STORE_H,
        markdown=0.0, recovered_fraction=1.0,
        why=(f"{km_to_store:.0f} km straight to {store.name}, skipping the hub and "
             f"{config.HANDOVER_WAREHOUSE_H:.0f} h of handling."))

    # D - sell today at a markdown, straight off the truck ---------------------
    add("D", destination=store, extra_km=km_to_store - remaining_km,
        warm_h=geo.drive_h(km_to_store), cold_h=0.0,
        markdown=config.MARKDOWN_FRACTION, recovered_fraction=1.0,
        why=(f"Sold at {store.name} today at -{config.MARKDOWN_FRACTION * 100:.0f} %: "
             f"no waste, part of the value recovered."))

    # E - donate while the food is still safe to eat ---------------------------
    bank, km_to_bank = geo.nearest_place(lat, lon, ("food_bank",))
    add("E", destination=bank, extra_km=km_to_bank - remaining_km,
        warm_h=geo.drive_h(km_to_bank), cold_h=0.0,
        markdown=(1.0 - config.DONATION_VALUE_FRACTION), recovered_fraction=1.0,
        why=(f"Handed to {bank.name} while it is still safe to eat: no revenue, "
             f"but the food is eaten instead of buried."))

    # F - hold in a cold room and decide later ---------------------------------
    # The load stops ageing fast once it is chilled, so shelf life is preserved;
    # what it costs is today's delivery slot.
    hold_warm_h = geo.drive_h(km_to_cold)
    add("F", destination=cold, extra_km=km_to_cold - remaining_km,
        warm_h=hold_warm_h, cold_h=0.0,
        markdown=config.HOLD_PENALTY_FRACTION, recovered_fraction=1.0,
        why=(f"Parked at {cold.name} after {km_to_cold:.0f} km: the clock slows to "
             f"normal and a person decides once the fault is understood."))

    ranked = sorted(options, key=lambda o: (o.score, o.life_on_arrival_h), reverse=True)
    best = ranked[0]
    baseline = options[0]                       # A, continue as planned
    if baseline.feasible and best.score - baseline.score < config.REROUTE_MIN_GAIN_QAR:
        best = baseline                         # do not move a shipment that is fine

    reasons = _review_reasons(options, ranked, best, sensor_ok)
    return Plan(truck_id=truck_id, product=product.product, qty_kg=qty_kg,
                product_c=product_c, air_c=air_c if air_c is not None else product_c,
                aging_speed=speed, life_left_h=life_left_h,
                min_life_on_arrival_h=product.min_life_on_arrival_h,
                options=options, recommended=best.key, generated_at=now,
                needs_human_review=bool(reasons), review_reasons=reasons,
                sensor_ok=sensor_ok)


def _review_reasons(options: list[Option], ranked: list[Option], best: Option,
                    sensor_ok: bool) -> list[str]:
    """Why the arithmetic alone should not settle this one.

    An empty list means the numbers are decisive and the system offers a
    recommendation. Anything in it means the dashboard asks a person to choose
    between sell, donate, hold and reroute instead.
    """
    reasons: list[str] = []
    if best.key == "A" and best.feasible:
        # Carrying on as planned changes nothing, so there is nothing to weigh.
        return reasons
    if not sensor_ok:
        reasons.append("The temperature reading cannot be trusted, so the freshness "
                       "numbers behind these options are unreliable.")
    if not any(o.feasible for o in options):
        reasons.append("No option meets the store's freshness minimum: whether to sell, "
                       "donate or hold is a commercial judgement, not arithmetic.")
    # Only a genuinely different course of action counts as a close call:
    # two ways to reroute are one decision, not two.
    rival = next((o for o in ranked if o.action != best.action), None)
    if rival is not None and abs(best.score - rival.score) < config.REVIEW_MARGIN_QAR:
        reasons.append(f"{ACTION_LABELS[best.action][0]} and "
                       f"{ACTION_LABELS[rival.action][0].lower()} are worth almost the same "
                       f"here, so the choice depends on things the system cannot see.")
    if best.action in ("sell", "donate") and best.revenue_qar >= config.REVIEW_VALUE_QAR:
        reasons.append("Selling off or donating a load this valuable is irreversible and "
                       "always goes to a person.")
    return reasons
