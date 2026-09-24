"""Shelf-life model (CLAUDE.md section 7.3).

Deterministic Python. The LLM never touches these numbers.

The model is the classic Q10 rule: for every 10 degrees above the ideal
storage temperature, food ages Q10 times faster.

    speed             = Q10 ** ((T - ideal_temp_c) / 10)
    life_left_h      -= dt_hours * DEMO_SPEED * speed
    hours_to_spoil    = life_left_h / speed
    life_on_arrival_h = life_left_h - remaining_trip_h * speed_on_the_way
    at_risk           = life_on_arrival_h < min_life_on_arrival_days * 24

`speed_on_the_way` defaults to 1.0, which reproduces the plain subtraction in
CLAUDE.md section 7.3 (a truck that is cooling normally ages at speed 1). The
planner passes the real speed when it assumes the cargo stays warm
(CLAUDE.md section 7.4).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache

from . import config


@dataclass(frozen=True)
class Product:
    """One row of data/products.csv."""

    product: str
    ideal_temp_c: float
    life_at_ideal_days: float
    q10: float
    alert_limit_c: float
    min_life_on_arrival_days: float
    value_qar_per_kg: float
    source_note: str = ""

    @property
    def life_at_ideal_h(self) -> float:
        return self.life_at_ideal_days * 24.0

    @property
    def min_life_on_arrival_h(self) -> float:
        return self.min_life_on_arrival_days * 24.0


@lru_cache(maxsize=1)
def load_products() -> dict[str, Product]:
    """Product rules from data/products.csv, keyed by product name."""
    out: dict[str, Product] = {}
    with open(config.DATA_DIR / "products.csv", newline="") as f:
        for row in csv.DictReader(f):
            out[row["product"]] = Product(
                product=row["product"],
                ideal_temp_c=float(row["ideal_temp_c"]),
                life_at_ideal_days=float(row["life_at_ideal_days"]),
                q10=float(row["q10"]),
                alert_limit_c=float(row["alert_limit_c"]),
                min_life_on_arrival_days=float(row["min_life_on_arrival_days"]),
                value_qar_per_kg=float(row["value_qar_per_kg"]),
                source_note=row.get("source_note", ""),
            )
    return out


def get_product(name: str) -> Product:
    """Product rules, falling back to lettuce so an unknown label never crashes."""
    products = load_products()
    if name in products:
        return products[name]
    return next(iter(products.values()))


def aging_speed(air_c: float, product: Product) -> float:
    """How many times faster than ideal the food is ageing right now."""
    return float(product.q10 ** ((air_c - product.ideal_temp_c) / 10.0))


def advance(life_left_h: float, dt_s: float, air_c: float, product: Product,
            demo_speed: float | None = None) -> float:
    """Consume shelf life for `dt_s` real seconds at `air_c`.

    `dt_s` is wall-clock seconds; the demo clock multiplies them.
    """
    speed = demo_speed if demo_speed is not None else config.DEMO_SPEED
    dt_hours = dt_s / 3600.0
    return max(0.0, life_left_h - dt_hours * speed * aging_speed(air_c, product))


def hours_to_spoil(life_left_h: float, air_c: float, product: Product) -> float:
    """Hours until the food is spoiled if it stays at this temperature."""
    return life_left_h / max(aging_speed(air_c, product), 1e-9)


def life_on_arrival_h(life_left_h: float, remaining_trip_h: float,
                      speed_on_the_way: float = 1.0) -> float:
    """Shelf life left at the moment the truck reaches its destination."""
    return life_left_h - remaining_trip_h * speed_on_the_way


def at_risk(life_on_arrival: float, product: Product) -> bool:
    """True when the store would refuse the load on arrival."""
    return life_on_arrival < product.min_life_on_arrival_h


def risk_level(life_on_arrival: float, product: Product) -> str:
    """green / amber / red, used for the map colours and the fleet list.

    green  the store will accept the load
    amber  below the store minimum but still rescuable (this is what the
           planner acts on)
    red    nothing left worth delivering
    """
    minimum = product.min_life_on_arrival_h
    if life_on_arrival <= 0 or life_on_arrival < minimum * 0.25:
        return "red"
    if life_on_arrival < minimum:
        return "amber"
    return "green"


def freshness_pct(life_left_h: float, product: Product) -> float:
    """Freshness score 0-100: shelf life left as a share of a perfect load."""
    return max(0.0, min(100.0, 100.0 * life_left_h / product.life_at_ideal_h))
