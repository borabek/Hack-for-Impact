"""logistics.py: the maths behind Safety Car (Person B).

Plain Python, no LLM, no network. Times, feasibility, cost, break-even and emissions are
all decided here (CLAUDE.md section 3: "the LLM reads; code decides").

Every option is judged for the case the product exists for: the unit FAILS its bench test.
  learn = shipment.bench_test_result_at  (the moment we know the unit will be late)
  ready = shipment.ready_if_test_fails   (the moment it can travel)

Offers, the scenario and OptionEval are the pydantic models in models.py. This module only
reads attributes, so it does not import models.py itself.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

UK = timezone.utc  # the scenario is in late November: UK time = UTC
CET = timezone(timedelta(hours=1))

STATUS_ORDER = {"bookable_now": 0, "fallback": 1, "conditional": 2, "blocked": 3}

# --------------------------------------------------------------------------- formatting


def fmt(dt: Optional[datetime]) -> str:
    """'Thu 09:00 CET'. A UTC offset of 0 is shown as 'UK', +1h as 'CET'. None -> 'n/a'."""
    if dt is None:
        return "n/a"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UK)
    off = dt.utcoffset() or timedelta(0)
    hours = off.total_seconds() / 3600
    if hours == 0:
        label = "UK"
    elif hours == 1:
        label = "CET"
    else:
        label = f"UTC{hours:+g}"
    return f"{dt:%a %H:%M} {label}"


def gbp(x: Optional[float], decimals: Optional[int] = None) -> str:
    """'£1,650'. Whole amounts have no decimals, others have two (e.g. '£577.50').
    Pass decimals=0 to round."""
    if x is None:
        return "n/a"
    if decimals is None:
        decimals = 0 if abs(x - round(x)) < 0.005 else 2
    return f"£{x:,.{decimals}f}"


def hours_text(h: Optional[float]) -> str:
    if h is None:
        return "n/a"
    return f"{h:g} h" if abs(h - round(h)) < 0.05 else f"{h:.1f} h"


# --------------------------------------------------------------------------- factors helpers


def fv(factors: Dict[str, Any], section: str, key: str) -> float:
    """Value of factors[section][key]['value'] (data/factors.json shape)."""
    return float(factors[section][key]["value"])


def ef(factors: Dict[str, Any], key: str) -> float:
    return fv(factors, "emission_factors", key)


def dist(factors: Dict[str, Any], key: str) -> float:
    return fv(factors, "distances_km", key)


def asm(factors: Dict[str, Any], key: str) -> float:
    return fv(factors, "assumptions", key)


# --------------------------------------------------------------------------- road time


def min_road_transit_h(km: float, avg_kmh: float, crew: Optional[int], factors: Dict[str, Any]) -> float:
    """Fastest legal door-to-door road time (EU drivers' hours, conservative).

    drive = km / avg_kmh. Driving per day is 18 h with two drivers (2 x 9 h; we do not assume
    both get 10 h days), otherwise 9 h. Total = full_days*24 + rest + a 45 min break per 4.5 h
    of driving + the Channel crossing. All values come from factors.json."""
    drive = km / avg_kmh
    per_day = asm(factors, "team_driving_h_per_day") if (crew or 1) >= 2 else asm(factors, "single_driver_daily_driving_h")
    full_days, rest = divmod(drive, per_day)
    brk = asm(factors, "break_h_per_4_5h")
    return full_days * 24 + rest + int(rest / 4.5) * brk + asm(factors, "channel_crossing_h")


# --------------------------------------------------------------------------- emissions


def emissions(offer: Any, scn: Any, factors: Dict[str, Any]) -> Tuple[float, str, float, bool]:
    """Modelled CO2e if this option is used: (kg, how it was worked out, dedicated_km, cross_border).

    groupage:  first mile (MK -> Daventry hub) x van factor + tonnes x Daventry->Monza x HGV tonne-km.
               dedicated_km = the first mile. Not cross-border (the truck was going anyway).
    van:       MK -> Monza x van factor, one way (empty return NOT counted). Cross-border.
    air:       (MK->LHR + MXP->Monza) x van factor + 2 x LHR->MXP flight km x flight factor
               (the courier's return flight). dedicated_km = the two ground legs. Cross-border.
    local hire: Milan depot -> Monza x van factor. Not cross-border."""
    van = ef(factors, "diesel_van_avg_kg_per_km")
    hgv = ef(factors, "hgv_artic_avg_laden_kg_per_tkm")
    flight = ef(factors, "short_haul_flight_kg_per_pkm")
    tonnes = scn.shipment.weight_kg / 1000.0
    mode = offer.mode

    if mode == "groupage_truck":
        first = dist(factors, "mk_to_daventry_hub")
        trunk = dist(factors, "daventry_to_monza")
        kg = first * van + tonnes * trunk * hgv
        how = (
            f"First mile {first:g} km x {van:.3f} kg/km (van) = {first * van:.1f} kg, plus the crate "
            f"({tonnes * 1000:g} kg = {tonnes:.3f} t) x {trunk:g} km x {hgv:.4f} kg/t-km (HGV trunk) "
            f"= {tonnes * trunk * hgv:.1f} kg. The truck was going to Monza anyway."
        )
        return kg, how, first, False
    if mode == "dedicated_van":
        km = dist(factors, "mk_to_monza")
        kg = km * van
        how = f"{km:g} km x {van:.3f} kg/km (whole van), one way. The van's empty return trip is not counted."
        return kg, how, km, True
    if mode == "air_courier":
        g1, g2 = dist(factors, "mk_to_lhr"), dist(factors, "mxp_to_monza")
        fl = dist(factors, "lhr_to_mxp_flight")
        kg = (g1 + g2) * van + 2 * fl * flight
        how = (
            f"Ground legs {g1 + g2:g} km x {van:.3f} kg/km = {(g1 + g2) * van:.1f} kg, plus the courier's "
            f"return flight 2 x {fl:g} km x {flight:.3f} kg/pkm = {2 * fl * flight:.1f} kg."
        )
        return kg, how, g1 + g2, True
    if mode == "local_hire":
        km = dist(factors, "milan_rental_to_monza")
        kg = km * van
        how = f"Delivery from the Milan depot: {km:g} km x {van:.3f} kg/km (van)."
        return kg, how, km, False
    return 0.0, "No emissions model for this mode.", 0.0, False


# --------------------------------------------------------------------------- evaluation


def _money_gbp(offer: Any, factors: Dict[str, Any]) -> Optional[float]:
    if offer.price_gbp is not None:
        return float(offer.price_gbp)
    if offer.price_eur is not None:
        return float(offer.price_eur) * asm(factors, "gbp_per_eur")
    return None


def _hours(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 3600.0


def evaluate(offer: Any, scn: Any, factors: Dict[str, Any], p_miss: float):
    """Judge one offer for the 'unit fails its bench test' case. Returns models.OptionEval."""
    from models import OptionEval  # local import: models.py is Person A's file

    ship = scn.shipment
    learn, ready, deadline = ship.bench_test_result_at, ship.ready_if_test_fails, ship.deadline
    issues: List[str] = []
    human: List[str] = []  # reasons a human must look before this can be bought automatically
    notes: List[str] = []
    departure: Optional[datetime] = None
    arrival: Optional[datetime] = None
    eta_plausible: bool = True  # no check for air/local hire: stated times are used
    mode = offer.mode

    # 1. booking windows that close before we even know the result
    if offer.latest_booking is not None and offer.latest_booking < learn:
        issues.append(f"Booking closes {fmt(offer.latest_booking)}, before the bench-test result ({fmt(learn)}).")
    if offer.confirm_by is not None and offer.confirm_by < learn:
        issues.append(f"The hold expires {fmt(offer.confirm_by)}, before the bench-test result ({fmt(learn)}).")

    # 2. time model per mode
    if mode == "dedicated_van":
        departure = max(learn + timedelta(hours=offer.collection_hours or 0), ready)
        if offer.transit_hours is not None:
            arrival = (departure + timedelta(hours=offer.transit_hours)).astimezone(CET)
            legal_min = min_road_transit_h(dist(factors, "mk_to_monza"), asm(factors, "van_avg_kmh"), offer.crew, factors)
            eta_plausible = offer.transit_hours >= 0.9 * legal_min
            if not eta_plausible:
                human.append(
                    f"ETA plausibility check failed: faster than EU drivers' hours rules allow "
                    f"({offer.transit_hours:g} h stated, about {legal_min:.0f} h legal minimum)."
                )
        else:
            human.append("No transit time stated: arrival cannot be worked out.")
    elif mode == "groupage_truck":
        first_mile = asm(factors, "first_mile_h")
        if offer.collection_cutoff is not None and ready + timedelta(hours=first_mile) > offer.collection_cutoff:
            issues.append(
                f"Unit is ready {fmt(ready)} + {first_mile:g} h to the hub, after the hub cut-off ({fmt(offer.collection_cutoff)})."
            )
        departure, arrival = offer.departure, offer.arrival
        if departure is not None and arrival is not None:
            stated_h = _hours(departure, arrival)
            legal_min = min_road_transit_h(dist(factors, "daventry_to_monza"), asm(factors, "hgv_avg_kmh"), offer.crew, factors)
            eta_plausible = stated_h >= 0.9 * legal_min
            if not eta_plausible:
                human.append(
                    f"ETA plausibility check failed: faster than EU drivers' hours rules allow "
                    f"({stated_h:.0f} h stated, about {legal_min:.0f} h legal minimum)."
                )
        else:
            human.append("Departure or arrival not stated: timing cannot be checked.")
        if offer.crew is None:
            notes.append("Crew not stated: the ETA check assumed a single driver's hours limit.")
    else:  # air_courier, local_hire: use the stated times
        departure, arrival = offer.departure, offer.arrival
        if arrival is None:
            human.append("No arrival time stated.")

    # 3. weight
    if offer.max_weight_kg_per_piece is not None and ship.weight_kg > offer.max_weight_kg_per_piece:
        issues.append(
            f"Crate weighs {ship.weight_kg:g} kg; the carrier takes at most {offer.max_weight_kg_per_piece:g} kg per piece."
        )

    # 4. small print
    for text in offer.limitations:
        low = text.lower()
        if "lithium" in low and ship.contains_lithium_battery:
            notes.append(f"Battery: {text}")
        if any(k in low for k in ("firmware", "compatib", "protocol")):
            human.append(f"Check before booking: {text}")
        if "deposit" in low:
            notes.append(f"Deposit: {text} (would need approval).")
        if "carnet" in low and not ship.carnet_listed:
            notes.append(
                "Condition before confirming: the unit is not on the ATA Carnet. Add it, or send a commercial "
                "invoice, before the carrier's paperwork cut-off."
            )

    # 5. spare time
    margin_h: Optional[float] = None
    on_time = False
    if arrival is not None:
        margin_h = _hours(arrival, deadline)
        on_time = margin_h >= 0
        if margin_h < 0:
            issues.append(f"Arrives {fmt(arrival)}, {abs(margin_h):.1f} h after the deadline ({fmt(deadline)}).")
        elif margin_h < asm(factors, "safe_margin_h"):
            notes.append(f"Only {margin_h:.1f} h spare: under the {asm(factors, 'safe_margin_h'):g} h comfort margin.")

    # 6. money
    price = _money_gbp(offer, factors)
    hold = offer.hold_fee_gbp
    cost_if_used = None if price is None else price + (hold or 0)
    if price is None:
        expected = None
    elif hold:
        expected = hold + p_miss * price
    else:
        expected = p_miss * price

    # 7. emissions
    co2e, how, ded_km, cross = emissions(offer, scn, factors)

    # 8. status: blocked > conditional > bookable_now (has a hold fee) > fallback
    if issues:
        status = "blocked"
    elif human:
        status = "conditional"
    elif hold:
        status = "bookable_now"
    else:
        status = "fallback"
    notes = [f"Needs a human check: {h}" for h in human] + notes

    return OptionEval(
        offer=offer,
        status=status,
        departure=departure,
        arrival=arrival,
        margin_h=margin_h,
        on_time=on_time,
        eta_plausible=eta_plausible,
        price_gbp=price,
        cost_if_used_gbp=cost_if_used,
        expected_cost_gbp=expected,
        co2e_kg=co2e,
        co2e_note=how,
        dedicated_km=ded_km,
        dedicated_cross_border_trip=cross,
        issues=issues,
        notes=notes,
    )


def evaluate_all(offers: List[Any], scn: Any, factors: Dict[str, Any], p_miss: float):
    """Evaluate every offer, sorted by status (bookable_now, fallback, conditional, blocked) then expected cost."""
    evals = [evaluate(o, scn, factors, p_miss) for o in offers]
    evals.sort(key=lambda e: (STATUS_ORDER[e.status], e.expected_cost_gbp if e.expected_cost_gbp is not None else 1e12))
    return evals


def breakeven_probability(hold: float, price_if_used: float, fallback_cost: float) -> Optional[float]:
    """The chance of a miss above which buying the hold beats waiting:
    hold = p x (fallback_cost - price_if_used). None if the hold never pays off."""
    gain = fallback_cost - price_if_used
    if gain <= 0 or hold is None:
        return None
    return hold / gain


# --------------------------------------------------------------------------- helpers for the UI


def decision_preview(hold: float, price_if_used: float, fallback_cost: float, p_miss: float) -> Tuple[str, Optional[float]]:
    """Sentence for the sidebar under the slider. Makes no payment."""
    be = breakeven_probability(hold, price_if_used, fallback_cost)
    if be is None:
        return "The hold never pays off against this fallback.", None
    if p_miss > be:
        return f"At {p_miss:.0%}: buy the hold (it pays off above {be:.1%}).", be
    return f"At {p_miss:.0%}: wait (the hold only pays off above {be:.1%}).", be


def impact(recommended: Any, baseline: Any, hold: float, p_miss: float) -> Dict[str, Any]:
    """Numbers for the impact card: usual plan (baseline) vs Safety Car (recommended).

    recommended / baseline are OptionEval. hold is the hold fee actually in force (60 or 120)."""
    r_cost = (recommended.price_gbp or 0) + hold
    b_cost = baseline.price_gbp or 0
    return {
        "cost_if_late_usual": b_cost,
        "cost_if_late_ours": r_cost,
        "saving_if_late": b_cost - r_cost,
        "cost_if_ok_usual": 0.0,
        "cost_if_ok_ours": hold,
        "expected_usual": p_miss * b_cost,
        "expected_ours": hold + p_miss * (recommended.price_gbp or 0),
        "breakeven": breakeven_probability(hold, recommended.price_gbp or 0, b_cost),
        "arrival_usual": baseline.arrival,
        "arrival_ours": recommended.arrival,
        "margin_usual_h": baseline.margin_h,
        "margin_ours_h": recommended.margin_h,
        "later_by_h": (_hours(baseline.arrival, recommended.arrival) if baseline.arrival and recommended.arrival else None),
        "co2e_usual": baseline.co2e_kg,
        "co2e_ours": recommended.co2e_kg,
        "km_usual": baseline.dedicated_km,
        "km_ours": recommended.dedicated_km,
        "trips_avoided": int(bool(baseline.dedicated_cross_border_trip) and not recommended.dedicated_cross_border_trip),
    }
