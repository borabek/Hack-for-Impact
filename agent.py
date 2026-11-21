"""Orchestration, decision, explanation (CLAUDE.md section 7). Owner: Person A.

The LLM reads (offers.py); this module decides, in plain Python: which options are viable, whether
holding now beats waiting, and what to ask payments.py to buy. payments.py enforces the money rules.

    from agent import load_scenario, load_factors, run
    scn, factors = load_scenario(), load_factors()
    result = run(scn, factors, Payments(scn.policy, scn.buyer), p_miss=0.35)
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

import llm
import logistics
from models import Offer, OptionEval, QuoteCheck, Scenario
from offers import (UPDATE_FILE, load_messages, merge_update, offer_id_for, parse_message, verify,
                    verify_merged)
from payments import Payments

DATA = Path(__file__).resolve().parent / "data"
KEY_FIELDS = ["carrier", "hold_fee_gbp", "price_gbp", "confirm_by"]  # must be verified to buy automatically


class Step(BaseModel):
    icon: str
    title: str
    detail: str = ""


class AgentRun(BaseModel):
    steps: list[Step] = Field(default_factory=list)
    offers: dict[str, Offer] = Field(default_factory=dict)            # offer_id -> offer (merged if fee_rise)
    checks: dict[str, list[QuoteCheck]] = Field(default_factory=dict)  # offer_id -> quote checks
    sources: dict[str, str] = Field(default_factory=dict)              # offer_id -> "llm" | "replayed"
    messages: dict[str, str] = Field(default_factory=dict)             # filename -> raw text
    files: dict[str, list[str]] = Field(default_factory=dict)          # offer_id -> filenames it was read from
    options: list[OptionEval] = Field(default_factory=list)
    recommended: Optional[str] = None   # offer_id of the hold we buy (or would buy)
    baseline: Optional[str] = None      # offer_id of the usual plan
    breakeven: Optional[float] = None   # chance of a miss above which the hold pays off
    decision: str = "wait"              # "hold" | "wait" | "needs_human"
    explanation: str = ""
    payment: dict = Field(default_factory=dict)  # status + ids
    impact: dict = Field(default_factory=dict)   # usual plan vs Safety Car, for the impact card
    extraction: str = "replayed"        # "llm" | "replayed" | "mixed"
    p_miss: float = 0.35
    fee_rise: bool = False
    scenario_label: str = ""            # "£60 hold" / "£120 hold"


# --------------------------------------------------------------------- loading

def load_scenario() -> Scenario:
    return Scenario.model_validate(json.loads((DATA / "scenario.json").read_text(encoding="utf-8")))


def load_factors() -> dict:
    return json.loads((DATA / "factors.json").read_text(encoding="utf-8"))


def gather_offers(use_llm: bool, fee_rise: bool) -> dict:
    """Parse every carrier message except the fee update; with fee_rise, merge the update into its offer
    (the changed fields' quotes are checked against the update message)."""
    messages = load_messages()
    offers, checks, sources, files = {}, {}, {}, {}
    for fn, text in messages.items():
        if fn == UPDATE_FILE:
            continue
        offer, src = parse_message(fn, text, use_llm)
        offers[offer.offer_id], sources[offer.offer_id], files[offer.offer_id] = offer, src, [fn]
        checks[offer.offer_id] = verify(offer, text)
    used = {fn for fns in files.values() for fn in fns}
    if fee_rise and UPDATE_FILE in messages:
        upd, src = parse_message(UPDATE_FILE, messages[UPDATE_FILE], use_llm)
        oid = offer_id_for(UPDATE_FILE)
        if oid in offers:
            base = offers[oid]
            offers[oid] = merge_update(base, upd)
            checks[oid] = verify_merged(base, upd, messages[files[oid][0]], messages[UPDATE_FILE])
            files[oid].append(UPDATE_FILE)
            sources[oid] = "llm" if sources[oid] == src == "llm" else "replayed"
            used.add(UPDATE_FILE)
    return {"offers": offers, "checks": checks, "sources": sources, "files": files,
            "messages": {fn: t for fn, t in messages.items() if fn in used}}


# --------------------------------------------------------------------- wording

def money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"£{x:,.0f}" if abs(x - round(x)) < 0.005 else f"£{x:,.2f}"


def pct(p: float, digits: int = 0) -> str:
    return f"{p * 100:.{digits}f}%"


def hours(h: Optional[float]) -> str:
    return "n/a" if h is None else f"{h:g} h" if float(h).is_integer() else f"{h:.1f} h"


def short_name(carrier: Optional[str]) -> str:
    return (carrier or "the carrier").split()[0].title() if carrier else "the carrier"


def short_item(item: str) -> str:
    words = re.sub(r"\s*\(.*?\)", "", item).split()
    return " ".join(words[-2:]).lower() if len(words) >= 2 else item.lower()


def _fallback_phrase(base: Optional[OptionEval]) -> str:
    if base is None:
        return "the usual emergency option"
    if base.offer.mode == "dedicated_van":
        return f"an emergency van at {money(base.cost_if_used_gbp)}"
    return f"{base.offer.carrier} at {money(base.cost_if_used_gbp)}"


def _reasons(ev: OptionEval, want_conditional: bool) -> str:
    if not want_conditional:
        return "; ".join(ev.issues) or "not viable"
    keys = ("firmware", "compatib", "protocol", "plausibility", "human")
    picked = [n for n in ev.notes if any(k in n.lower() for k in keys)] or ev.notes or ["needs a human check"]
    picked = [re.sub(r"^needs a human( check)?:\s*", "", n, flags=re.I) for n in picked]
    return "; ".join(dict.fromkeys(picked))


def _plan_c(options: list[OptionEval]) -> str:
    out = []
    for ev in options:
        if ev.status == "conditional" and ev.arrival is not None:
            out.append(f"Plan C: {ev.offer.carrier} could have a unit at Monza by {logistics.fmt(ev.arrival)} for "
                       f"about {money(round(ev.cost_if_used_gbp or 0))}, but it needs a human check first "
                       f"({_reasons(ev, True)}).")
    return " ".join(out)


def explain(scn: Scenario, rec: OptionEval, base: Optional[OptionEval], breakeven: float, p_miss: float,
            over_limit: bool, fee_rise: bool, options: list[OptionEval]) -> str:
    """The explanation template from CLAUDE.md. Every number comes from the calculation."""
    who, item = short_name(rec.offer.carrier), short_item(scn.shipment.item)
    hold, limit = rec.offer.hold_fee_gbp, scn.policy.per_call_limit_gbp
    body = (f"If the {item} misses the truck ({pct(p_miss)} estimated), this slot still gets it to Monza by "
            f"{logistics.fmt(rec.arrival)} for {money(rec.price_gbp)} more, instead of {_fallback_phrase(base)}. "
            f"The hold pays for itself above a {pct(breakeven)} chance of a miss.")
    plan_c = _plan_c(options)
    if over_limit:
        verb = "now wants" if fee_rise else "wants"
        parts = [f"{who} {verb} {money(hold)} to hold the slot, above your {money(limit)} per-hold limit, so I "
                 f"need your approval.", body, plan_c,
                 "If you decline, I'll wait for the bench test and book the van only if it's needed."]
    else:
        parts = [f"Booking a {money(hold)} hold with {who}, within your {money(limit)} limit.", body, plan_c]
    return " ".join(p for p in parts if p)


def explain_wait(scn: Scenario, rec: OptionEval, base: Optional[OptionEval], breakeven: float, p_miss: float) -> str:
    return (f"Waiting: at a {pct(p_miss)} chance of a miss, a {money(rec.offer.hold_fee_gbp)} hold with "
            f"{short_name(rec.offer.carrier)} costs more than it saves. It only pays off above "
            f"{pct(breakeven, 1)}. If the {short_item(scn.shipment.item)} fails its bench test at "
            f"{logistics.fmt(scn.shipment.bench_test_result_at)}, I'll book {_fallback_phrase(base)} then.")


# ---------------------------------------------------------------------- impact

def build_impact(rec: Optional[OptionEval], base: Optional[OptionEval], breakeven: Optional[float],
                 scenario_label: str) -> dict:
    if rec is None or base is None:
        return {}

    def side(ev: OptionEval, hold_fee: float) -> dict:
        return {
            "offer_id": ev.offer.offer_id, "carrier": ev.offer.carrier, "mode": ev.offer.mode,
            "cost_if_late_gbp": ev.cost_if_used_gbp, "cost_if_not_late_gbp": hold_fee,
            "expected_cost_gbp": ev.expected_cost_gbp,
            "arrival": ev.arrival, "arrival_label": logistics.fmt(ev.arrival) if ev.arrival else "n/a",
            "margin_h": ev.margin_h, "dedicated_km": ev.dedicated_km,
            "dedicated_cross_border_trip": ev.dedicated_cross_border_trip,
            "co2e_kg": ev.co2e_kg, "co2e_note": ev.co2e_note,
        }

    ours, usual = side(rec, rec.offer.hold_fee_gbp or 0), side(base, base.offer.hold_fee_gbp or 0)
    trips = int(base.dedicated_cross_border_trip) - int(rec.dedicated_cross_border_trip)
    later_h = (rec.arrival - base.arrival).total_seconds() / 3600 if rec.arrival and base.arrival else None
    return {
        "scenario": scenario_label,
        "ours": ours, "usual": usual,
        "dedicated_cross_border_trips_avoided": max(trips, 0),
        "headline": f"{max(trips, 0)} dedicated cross-border trip{'s' if trips != 1 else ''} avoided",
        "saving_if_late_gbp": (base.cost_if_used_gbp or 0) - (rec.cost_if_used_gbp or 0),
        "expected_saving_gbp": (base.expected_cost_gbp or 0) - (rec.expected_cost_gbp or 0),
        "arrives_later_than_usual_h": later_h,
        "co2e_saving_kg": (base.co2e_kg or 0) - (rec.co2e_kg or 0),
        "breakeven": breakeven,
        "co2e_label": "modelled estimate",
    }


# ------------------------------------------------------------------------- run

def _verified_fields(checks: list[QuoteCheck]) -> dict[str, bool]:
    return {c.field: c.verified for c in checks}


def run(scn: Scenario, factors: dict, payments: Payments, *, p_miss: float, fee_rise: bool = False,
        use_llm: bool = False) -> AgentRun:
    g = gather_offers(use_llm, fee_rise)
    offers, checks = g["offers"], g["checks"]
    r = AgentRun(offers=offers, checks=checks, sources=g["sources"], messages=g["messages"], files=g["files"],
                 p_miss=p_miss, fee_rise=fee_rise, baseline=scn.baseline_offer_id)
    srcs = set(g["sources"].values())
    r.extraction = srcs.pop() if len(srcs) == 1 else "mixed"
    s = scn.shipment
    steps = r.steps

    # 🚨 shipment at risk
    steps.append(Step(icon="🚨", title=f"Shipment at risk: {s.item}",
                      detail=f"{pct(p_miss)} chance it misses the {logistics.fmt(s.main_truck_departure)} truck "
                             f"(bench-test result {logistics.fmt(s.bench_test_result_at)}). Deadline "
                             f"{logistics.fmt(s.deadline)} at Monza. {s.weight_kg:g} kg crate."))

    # 📨 read the messages
    n_ok = sum(c.verified for cs in checks.values() for c in cs)
    n_all = sum(len(cs) for cs in checks.values())
    how = {"llm": f"live AI extraction ({llm.label()})", "replayed": "replayed extraction",
           "mixed": "live AI extraction, with replayed fallback for some messages"}[r.extraction]
    upd = " (incl. a fee update)" if fee_rise and UPDATE_FILE in g["messages"] else ""
    steps.append(Step(icon="📨", title=f"Read {len(g['messages'])} carrier messages{upd}",
                      detail=f"{n_ok}/{n_all} quotes verified against the original words · {how}"))

    # 🛡️ instructions found inside messages
    for oid, offer in offers.items():
        for flag in offer.flags:
            steps.append(Step(icon="🛡️", title=f"Ignored an instruction inside {offer.carrier}'s message",
                              detail=flag if "policy" in flag.lower() else
                              f"{flag} Spend limits come only from {scn.policy.owner}'s policy, enforced in code."))

    options = logistics.evaluate_all(list(offers.values()), scn, factors, p_miss)
    r.options = options
    by_id = {ev.offer.offer_id: ev for ev in options}
    base = by_id.get(scn.baseline_offer_id)

    # ⛔ ruled out
    for ev in options:
        if ev.status == "blocked":
            steps.append(Step(icon="⛔", title=f"Ruled out {ev.offer.carrier}", detail=_reasons(ev, False)))

    # ❓ needs a human: conditional options, and bookable options with unverified key quotes
    for ev in options:
        if ev.status == "conditional":
            steps.append(Step(icon="❓", title=f"{ev.offer.carrier} needs a human check",
                              detail=_reasons(ev, True)))
    candidates = []
    for ev in options:
        if ev.status != "bookable_now" or not ev.on_time:
            continue
        ver = _verified_fields(checks.get(ev.offer.offer_id, []))
        missing = [f for f in KEY_FIELDS if not ver.get(f, False)]
        if missing:
            steps.append(Step(icon="❓", title=f"{ev.offer.carrier} needs a human check before buying",
                              detail=f"No verified quote for {', '.join(missing)}, so the agent won't buy it "
                                     f"automatically."))
        else:
            candidates.append(ev)

    rec = min(candidates, key=lambda e: e.expected_cost_gbp) if candidates else None
    if rec is None:
        r.decision = "needs_human"
        r.explanation = ("No option can be bought automatically: every hold needs a human check first. "
                         "Nothing was purchased.")
        r.payment = {"status": "needs_human"}
        steps.append(Step(icon="🛑", title="No automatic purchase", detail=r.explanation))
        _next_actions(r, scn, None)
        return r

    r.recommended = rec.offer.offer_id
    r.scenario_label = f"{money(rec.offer.hold_fee_gbp)} hold"
    fallback_cost = base.cost_if_used_gbp if base and base.cost_if_used_gbp else None
    if fallback_cost is None or fallback_cost <= (rec.price_gbp or 0):
        r.breakeven = 1.0  # the hold can never pay off against this fallback
    else:
        r.breakeven = logistics.breakeven_probability(rec.offer.hold_fee_gbp, rec.price_gbp, fallback_cost)

    # 🧮 waiting vs holding now
    steps.append(Step(icon="🧮", title="Waiting vs holding now",
                      detail=f"Wait: expected {money(base.expected_cost_gbp if base else None)} "
                             f"({pct(p_miss)} × {money(fallback_cost)} {'van' if base and base.offer.mode == 'dedicated_van' else 'fallback'}). "
                             f"Hold now: expected {money(rec.expected_cost_gbp)} ({money(rec.offer.hold_fee_gbp)} + "
                             f"{pct(p_miss)} × {money(rec.price_gbp)}). The hold pays off above a "
                             f"{pct(r.breakeven, 1)} chance of a miss."))
    r.impact = build_impact(rec, base, r.breakeven, r.scenario_label)

    if p_miss <= r.breakeven:
        r.decision = "wait"
        r.explanation = explain_wait(scn, rec, base, r.breakeven, p_miss)
        r.payment = {"status": "none"}
        steps.append(Step(icon="⏸️", title="Wait: no purchase", detail=r.explanation))
        _next_actions(r, scn, rec)
        return r

    r.decision = "hold"
    offer = rec.offer
    preview = payments.preview_policy(offer.carrier, offer.hold_fee_gbp, scn.policy.purpose, scn.now)
    r.explanation = explain(scn, rec, base, r.breakeven, p_miss, preview.status == "needs_approval", fee_rise,
                            options)
    not_included = f"Transport {money(rec.price_gbp)}, billed only if the slot is used"
    if any("carnet" in n.lower() for n in rec.notes) or (
            not s.carnet_listed and any("carnet" in x.lower() for x in offer.limitations)):
        not_included += ". Before confirming: the unit must be on the ATA Carnet, or a commercial invoice sent"
    res = payments.reserve(
        offer_id=offer.offer_id, merchant=offer.carrier, amount=offer.hold_fee_gbp,
        what_for=f"Holding fee: reserves {offer.service} until {logistics.fmt(offer.confirm_by)}",
        not_included=not_included, cancellation=offer.cancellation_terms or "", purpose=scn.policy.purpose,
        reason=r.explanation, at=scn.now,
    )
    status = res["status"]
    r.payment = {"status": status, "amount_gbp": offer.hold_fee_gbp, "merchant": offer.carrier}
    if res.get("hold"):
        r.payment["hold_id"] = res["hold"].hold_id
    if res.get("receipt"):
        r.payment["receipt_id"] = res["receipt"].receipt_id
    if res.get("approval"):
        r.payment["approval_id"] = res["approval"].approval_id
    if status in ("booked", "already_held"):
        steps.append(Step(icon="✅", title=f"Booked a {money(offer.hold_fee_gbp)} hold with {offer.carrier}",
                          detail=f"Within {scn.policy.owner}'s {money(scn.policy.per_call_limit_gbp)} policy, paid "
                                 f"automatically. Receipt {r.payment.get('receipt_id', '')} (simulated)."
                                 if status == "booked" else "A hold is already active; no second charge."))
    elif status == "approval_requested":
        a = res["approval"]
        steps.append(Step(icon="📱", title=f"Asked {scn.policy.owner} to approve {money(a.amount_gbp)}",
                          detail="; ".join(a.policy_reasons) + ". The agent can't approve its own request."))
    else:
        r.payment["reasons"] = res["decision"].reasons
        steps.append(Step(icon="🛑", title="Blocked by policy", detail="; ".join(res["decision"].reasons)))
    _next_actions(r, scn, rec)
    return r


def _next_actions(r: AgentRun, scn: Scenario, rec: Optional[OptionEval]) -> None:
    actions = []
    s = scn.shipment
    if rec is not None:
        carnet = [x for x in rec.offer.limitations if "carnet" in x.lower()]
        if carnet and not s.carnet_listed:
            actions.append(f"Add the {short_item(s.item)} to the ATA Carnet, or send "
                           f"{short_name(rec.offer.carrier)} a commercial invoice ({carnet[0]}).")
        if r.decision == "hold":
            actions.append(f"If the unit passes its bench test ({logistics.fmt(s.bench_test_result_at)}) and makes "
                           f"the truck, release the hold.")
            actions.append(f"If it fails, confirm the slot by {logistics.fmt(rec.offer.confirm_by)}: "
                           f"{money(rec.price_gbp)} transport, which needs {scn.policy.owner}'s approval."
                           if (rec.price_gbp or 0) > scn.policy.per_call_limit_gbp else
                           f"If it fails, confirm the slot by {logistics.fmt(rec.offer.confirm_by)}.")
    if r.decision != "hold":
        actions.append(f"Wait for the bench-test result at {logistics.fmt(s.bench_test_result_at)}.")
    r.steps.append(Step(icon="📋", title="Next actions", detail=" · ".join(actions)))


# ------------------------------------------------------------- the late branch

def _trunk(offer: Offer) -> str:
    m = re.search(r"\b[A-Z]{2,}-\d+\b", " ".join([offer.service or ""] + list(offer.evidence.values())))
    return m.group(0) if m else (offer.carrier or "the carrier")


def _hub(offer: Offer) -> str:
    m = re.search(r"([A-Z][a-z]+) hub", " ".join([offer.service or ""] + list(offer.evidence.values())))
    return m.group(1) if m else "the hub"


def _active_hold(payments: Payments):
    for h in reversed(payments.holds):
        if h.status == "held":
            return h
    return None


def confirm_slot(scn: Scenario, factors: dict, payments: Payments, *, paperwork_done: bool,
                 at: Optional[datetime] = None) -> dict:
    """Bench test failed: confirm the held slot. Paperwork first, then the transport charge goes
    through the spend policy (over the limit -> Sarah approves)."""
    hold = _active_hold(payments)
    if hold is None:
        return {"status": "no_active_hold"}
    offers = gather_offers(use_llm=False, fee_rise=False)["offers"]
    offer = offers.get(hold.offer_id)
    if offer is None or offer.price_gbp is None:
        return {"status": "no_offer", "hold": hold}
    ev = logistics.evaluate(offer, scn, factors, scn.shipment.p_miss_main_truck)
    base_offer = offers.get(scn.baseline_offer_id)
    base = logistics.evaluate(base_offer, scn, factors, scn.shipment.p_miss_main_truck) if base_offer else None
    limit = scn.policy.per_call_limit_gbp
    over = offer.price_gbp > limit
    what_for = (f"Transport: confirms the held slot on {_trunk(offer)}, collection {_hub(offer)} "
                f"{logistics.fmt(offer.collection_cutoff)}, ETA {logistics.fmt(ev.arrival)}")
    reason = (f"The unit failed its bench test. Confirming the slot costs {money(offer.price_gbp)}, "
              f"{'over' if over else 'within'} your {money(limit)} limit. It still reaches Monza "
              f"{logistics.fmt(ev.arrival)}, {hours(ev.margin_h)} before the deadline, instead of "
              f"{_fallback_phrase(base)}.")
    res = payments.confirm(hold.hold_id, amount=offer.price_gbp, what_for=what_for, paperwork_done=paperwork_done,
                           purpose=scn.policy.purpose, reason=reason, at=at or scn.now,
                           cancellation=offer.cancellation_terms or "")
    res["what_for"], res["reason"] = what_for, reason
    return res


def release_hold(scn: Scenario, payments: Payments, at: Optional[datetime] = None):
    """Bench test passed: the unit makes the truck, so release the hold (the fee is the insurance)."""
    hold = _active_hold(payments)
    return payments.release(hold.hold_id, at=at or scn.now) if hold else None


def confirmation_card(scn: Scenario, factors: dict, payments: Payments) -> Optional[dict]:
    """Carrier confirmation card data once a slot is confirmed (ref, collection, ETA)."""
    used = [h for h in payments.holds if h.status == "used" and h.confirmation_ref]
    if not used:
        return None
    hold = used[-1]
    offer = gather_offers(use_llm=False, fee_rise=False)["offers"].get(hold.offer_id)
    if offer is None:
        return {"ref": hold.confirmation_ref, "carrier": hold.merchant}
    ev = logistics.evaluate(offer, scn, factors, scn.shipment.p_miss_main_truck)
    return {
        "ref": hold.confirmation_ref, "carrier": offer.carrier, "trunk": _trunk(offer),
        "collection": f"{_hub(offer)} {logistics.fmt(offer.collection_cutoff)}",
        "departure": logistics.fmt(offer.departure) if offer.departure else None,
        "eta": logistics.fmt(ev.arrival), "margin_h": ev.margin_h,
        "receipt": payments.transport_receipt(hold.hold_id),
    }
