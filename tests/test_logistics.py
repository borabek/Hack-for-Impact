"""PROMPT B1: reproduce the expected-results table in CLAUDE.md section 8 (p_miss = 0.35)."""
import json
from datetime import timedelta
from pathlib import Path

import pytest

import logistics as lg
from models import Offer, Scenario

DATA = Path(__file__).resolve().parent.parent / "data"


def _load():
    scn = Scenario.model_validate_json((DATA / "scenario.json").read_text(encoding="utf-8"))
    factors = json.loads((DATA / "factors.json").read_text(encoding="utf-8"))
    raw = json.loads((DATA / "expected_offers.json").read_text(encoding="utf-8"))
    offers = {}
    for fname, fields in raw.items():
        oid = fname.split("_")[0]
        offers[fname] = Offer(offer_id=oid, source_file=fname, **fields)
    return scn, factors, offers


@pytest.fixture(scope="module")
def world():
    return _load()


@pytest.fixture(scope="module")
def evals(world):
    scn, factors, offers = world
    base = [o for f, o in offers.items() if f != "nordlink_update.txt"]
    return {e.offer.offer_id: e for e in lg.evaluate_all(base, scn, factors, 0.35)}


# ----------------------------------------------------------------- table in CLAUDE.md section 8

def test_sort_order(world):
    scn, factors, offers = world
    base = [o for f, o in offers.items() if f != "nordlink_update.txt"]
    order = [e.offer.offer_id for e in lg.evaluate_all(base, scn, factors, 0.35)]
    assert order == ["nordlink", "swiftvan", "milano", "aerodash"]


def test_nordlink(evals):
    e = evals["nordlink"]
    assert e.status == "bookable_now"
    assert lg.fmt(e.arrival) == "Thu 09:00 CET"
    assert e.margin_h == pytest.approx(9)
    assert e.on_time and e.eta_plausible
    assert e.cost_if_used_gbp == pytest.approx(400)
    assert e.expected_cost_gbp == pytest.approx(179)
    assert e.co2e_kg == pytest.approx(17.2, abs=1)
    assert e.dedicated_km == 50 and not e.dedicated_cross_border_trip
    # the carnet is a condition to confirm, not a reason to skip the hold
    assert any("Carnet" in n for n in e.notes)
    assert not e.issues


def test_swiftvan_baseline(evals):
    e = evals["swiftvan"]
    assert e.status == "fallback"
    assert lg.fmt(e.arrival) == "Wed 14:00 CET"
    assert e.margin_h == pytest.approx(28)
    assert e.cost_if_used_gbp == pytest.approx(1650)
    assert e.expected_cost_gbp == pytest.approx(577.5)
    assert e.co2e_kg == pytest.approx(314.4, abs=1)
    assert e.dedicated_cross_border_trip and e.dedicated_km == 1230
    assert e.eta_plausible


def test_milano_needs_firmware_check(evals):
    e = evals["milano"]
    assert e.status == "conditional"
    assert lg.fmt(e.arrival) == "Wed 16:00 CET"
    assert e.margin_h == pytest.approx(26)
    assert e.cost_if_used_gbp == pytest.approx(447, abs=1)
    assert e.expected_cost_gbp == pytest.approx(157, abs=1)
    assert e.co2e_kg == pytest.approx(6.4, abs=1)
    assert any("firmware" in n.lower() for n in e.notes)
    assert any("deposit" in n.lower() for n in e.notes)


def test_aerodash_blocked_by_weight(evals):
    e = evals["aerodash"]
    assert e.status == "blocked"
    assert any("45 kg" in i and "32 kg" in i for i in e.issues)
    assert lg.fmt(e.arrival) == "Thu 12:30 CET"
    assert e.margin_h == pytest.approx(5.5)
    assert e.cost_if_used_gbp == pytest.approx(2900)
    assert e.expected_cost_gbp == pytest.approx(1015)
    assert e.co2e_kg == pytest.approx(325.7, abs=1)
    assert any("Battery" in n for n in e.notes)


def test_breakeven_probabilities():
    assert lg.breakeven_probability(60, 340, 1650) == pytest.approx(0.046, abs=0.001)
    assert lg.breakeven_probability(120, 340, 1650) == pytest.approx(0.092, abs=0.001)
    assert lg.breakeven_probability(60, 2000, 1650) is None


# ----------------------------------------------------------------- the 120 pound replay

def test_fee_rise_numbers(world):
    scn, factors, offers = world
    nl = offers["nordlink_groupage_email.txt"].model_copy(update={"hold_fee_gbp": 120})
    e = lg.evaluate(nl, scn, factors, 0.35)
    assert e.cost_if_used_gbp == pytest.approx(460)
    assert e.expected_cost_gbp == pytest.approx(239)


def test_impact_card_numbers(world, evals):
    imp = lg.impact(evals["nordlink"], evals["swiftvan"], hold=60, p_miss=0.35)
    assert imp["cost_if_late_ours"] == 400 and imp["cost_if_late_usual"] == 1650
    assert imp["later_by_h"] == pytest.approx(19)
    assert imp["trips_avoided"] == 1
    assert imp["expected_ours"] == pytest.approx(179)
    imp120 = lg.impact(evals["nordlink"], evals["swiftvan"], hold=120, p_miss=0.35)
    assert imp120["cost_if_late_ours"] == 460
    assert imp120["expected_ours"] == pytest.approx(239)
    assert imp120["breakeven"] == pytest.approx(0.092, abs=0.001)


# ----------------------------------------------------------------- rules and edge cases

def test_van_booking_window_closes_before_test_result(world):
    scn, factors, offers = world
    sv = offers["swiftvan_whatsapp.txt"].model_copy(
        update={"latest_booking": scn.shipment.bench_test_result_at - timedelta(hours=1)}
    )
    e = lg.evaluate(sv, scn, factors, 0.35)
    assert e.status == "blocked" and e.issues


def test_implausibly_fast_van_needs_human(world):
    scn, factors, offers = world
    sv = offers["swiftvan_whatsapp.txt"].model_copy(update={"transit_hours": 12})
    e = lg.evaluate(sv, scn, factors, 0.35)
    assert e.eta_plausible is False
    assert e.status == "conditional"
    assert any("plausibility" in n.lower() for n in e.notes)


def test_late_arrival_is_blocked(world):
    scn, factors, offers = world
    nl = offers["nordlink_groupage_email.txt"]
    late = nl.model_copy(update={"arrival": scn.shipment.deadline + timedelta(hours=2)})
    e = lg.evaluate(late, scn, factors, 0.35)
    assert e.status == "blocked" and not e.on_time


def test_groupage_cutoff_before_unit_is_ready(world):
    scn, factors, offers = world
    nl = offers["nordlink_groupage_email.txt"].model_copy(
        update={"collection_cutoff": scn.shipment.ready_if_test_fails}
    )
    e = lg.evaluate(nl, scn, factors, 0.35)
    assert e.status == "blocked"


def test_hold_expires_before_test_result(world):
    scn, factors, offers = world
    nl = offers["nordlink_groupage_email.txt"].model_copy(
        update={"confirm_by": scn.shipment.bench_test_result_at - timedelta(minutes=1)}
    )
    assert lg.evaluate(nl, scn, factors, 0.35).status == "blocked"


def test_min_road_transit(world):
    _, factors, _ = world
    # 1230 km at 85 km/h with two drivers: 14.47 h + 3 breaks (2.25 h) + 2.5 h Channel = 19.2 h
    assert lg.min_road_transit_h(1230, 85, 2, factors) == pytest.approx(19.22, abs=0.05)
    # one driver can only drive 9 h a day, so the same trip needs an overnight rest
    assert lg.min_road_transit_h(1230, 85, 1, factors) > 30


def test_formatting():
    from datetime import datetime, timezone
    assert lg.fmt(datetime(2026, 11, 26, 9, 0, tzinfo=timezone(timedelta(hours=1)))) == "Thu 09:00 CET"
    assert lg.fmt(datetime(2026, 11, 24, 21, 0, tzinfo=timezone.utc)) == "Tue 21:00 UK"
    assert lg.gbp(1650) == "£1,650"
    assert lg.gbp(577.5) == "£577.50"
    assert lg.gbp(446.9, 0) == "£447"


def test_decision_preview():
    text, be = lg.decision_preview(60, 340, 1650, 0.35)
    assert "buy the hold" in text and be == pytest.approx(0.0458, abs=0.001)
    text2, _ = lg.decision_preview(60, 340, 1650, 0.02)
    assert "wait" in text2
