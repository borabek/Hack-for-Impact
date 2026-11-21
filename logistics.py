"""Time, feasibility, cost, break-even and emissions (CLAUDE.md section 7). Owner: Person B.

Stub created by the scaffold: Person B implements it (PROMPT B1).
"""
from __future__ import annotations

from datetime import datetime

from models import Offer, OptionEval, Scenario


def fmt(dt: datetime) -> str:
    raise NotImplementedError


def gbp(x: float) -> str:
    raise NotImplementedError


def min_road_transit_h(km: float, avg_kmh: float, crew: int | None, factors: dict) -> float:
    raise NotImplementedError


def emissions(offer: Offer, scn: Scenario, factors: dict) -> tuple[float, str, float, bool]:
    raise NotImplementedError


def evaluate(offer: Offer, scn: Scenario, factors: dict, p_miss: float) -> OptionEval:
    raise NotImplementedError


def evaluate_all(offers: list[Offer], scn: Scenario, factors: dict, p_miss: float) -> list[OptionEval]:
    raise NotImplementedError


def breakeven_probability(hold: float, price_if_used: float, fallback_cost: float) -> float:
    raise NotImplementedError
