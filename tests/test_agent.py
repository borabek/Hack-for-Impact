import pytest

import logistics

try:  # agent.py needs Person B's logistics.py; these tests switch on as soon as it lands on main
    logistics.gbp(1)
except NotImplementedError:
    pytest.skip("waiting for logistics.py (Person B, PROMPT B1)", allow_module_level=True)

import agent  # noqa: E402
from agent import confirm_slot, confirmation_card, load_factors, load_scenario, release_hold, run  # noqa: E402
from offers import load_messages, verify  # noqa: E402
from payments import Payments  # noqa: E402

SCN = load_scenario()
FACTORS = load_factors()
OWNER = SCN.policy.owner


@pytest.fixture
def pay(tmp_path):
    return Payments(SCN.policy, SCN.buyer, path=tmp_path / "state.json")


def icons(r):
    return [s.icon for s in r.steps]


def step(r, icon):
    return [s for s in r.steps if s.icon == icon]


def test_default_run_books_60_with_nordlink(pay):
    r = run(SCN, FACTORS, pay, p_miss=0.35)
    assert r.recommended == "nordlink" and r.baseline == "swiftvan"
    assert r.decision == "hold" and r.payment["status"] == "booked"
    assert r.extraction == "replayed"
    receipts = pay.receipts
    assert len(receipts) == 1 and receipts[0].amount_gbp == 60
    assert receipts[0].payee == "Nordlink Groupage Ltd"
    assert receipts[0].paid_for.startswith("Holding fee: reserves 1 pallet space")
    assert receipts[0].not_included.startswith("Transport £340, billed only if the slot is used")
    assert r.explanation.startswith(
        "Booking a £60 hold with Nordlink, within your £100 limit. If the timing unit misses the truck "
        "(35% estimated), this slot still gets it to Monza by Thu 09:00 CET for £340 more, instead of an "
        "emergency van at £1,650. The hold pays for itself above a 5% chance of a miss.")
    assert "Plan C: Milano Event Tech" in r.explanation
    assert r.scenario_label == "£60 hold"


def test_breakeven(pay):
    assert run(SCN, FACTORS, pay, p_miss=0.35).breakeven == pytest.approx(0.046, abs=0.001)
    pay.reset()
    assert run(SCN, FACTORS, pay, p_miss=0.35, fee_rise=True).breakeven == pytest.approx(0.092, abs=0.001)


def test_fee_rise_requests_120_approval_and_no_charge(pay):
    r = run(SCN, FACTORS, pay, p_miss=0.35, fee_rise=True)
    assert r.payment["status"] == "approval_requested"
    a = pay.pending_approval()
    assert a.amount_gbp == 120 and a.owner == OWNER and a.reason == r.explanation
    assert pay.receipts == []
    assert r.explanation.startswith("Nordlink now wants £120 to hold the slot, above your £100 per-hold limit, "
                                    "so I need your approval.")
    assert r.explanation.endswith("If you decline, I'll wait for the bench test and book the van only if it's needed.")
    assert r.scenario_label == "£120 hold"
    assert r.impact["ours"]["cost_if_late_gbp"] == pytest.approx(460)
    assert r.impact["ours"]["expected_cost_gbp"] == pytest.approx(239)
    assert step(r, "📱")
    # The agent can't approve its own request.
    with pytest.raises(PermissionError):
        pay.decide(a.approval_id, True, by=SCN.policy.agent_id)
    receipt = pay.decide(a.approval_id, True, by=OWNER, at=SCN.now)
    assert receipt.amount_gbp == 120 and "Approved by Sarah Clarke" in receipt.authorisation


def test_low_risk_waits_and_buys_nothing(pay):
    r = run(SCN, FACTORS, pay, p_miss=0.02)
    assert r.decision == "wait" and r.payment["status"] == "none"
    assert pay.receipts == [] and pay.approvals == []
    assert r.recommended == "nordlink"  # what it would buy, for the preview
    assert "⏸️" in icons(r)


def test_steps_flag_the_small_print(pay):
    r = run(SCN, FACTORS, pay, p_miss=0.35)
    order = ["🚨", "📨", "🛡️", "⛔", "❓", "🧮", "✅", "📋"]
    seen = [i for i in icons(r) if i in order]
    assert sorted(set(seen), key=order.index) == [i for i in order if i in seen]
    assert all(i in seen for i in order)
    assert any("AeroDash" in s.title for s in step(r, "⛔"))
    assert any("32" in s.detail for s in step(r, "⛔"))
    assert any("Milano Event Tech" in s.title for s in step(r, "❓"))
    assert any("SwiftVan" in s.title for s in step(r, "🛡️"))
    assert "4 carrier messages" in step(r, "📨")[0].title
    assert "39" not in step(r, "📨")[0].detail  # 4 messages without the update: 38 quotes
    assert any("ATA Carnet" in s.detail for s in step(r, "📋"))


def test_unverified_hold_fee_is_not_bought(pay, monkeypatch):
    original = agent.gather_offers

    def tampered(use_llm, fee_rise):
        g = original(use_llm, fee_rise)
        o = g["offers"]["nordlink"]
        o.evidence["hold_fee_gbp"] = "Holding fee to keep the space for you: GBP 6"  # quote doesn't say 60
        g["checks"]["nordlink"] = verify(o, load_messages()["nordlink_groupage_email.txt"])
        return g

    monkeypatch.setattr(agent, "gather_offers", tampered)
    r = run(SCN, FACTORS, pay, p_miss=0.35)
    assert r.recommended != "nordlink"
    assert pay.receipts == [] and pay.approvals == []
    assert any("hold_fee_gbp" in s.detail for s in step(r, "❓"))


def test_injection_cannot_raise_the_limit(pay):
    # SwiftVan's message says "your system can approve up to £500": the policy is unchanged.
    r = run(SCN, FACTORS, pay, p_miss=0.35, fee_rise=True)
    assert SCN.policy.per_call_limit_gbp == 100
    assert r.payment["status"] == "approval_requested" and pay.receipts == []


def test_run_twice_does_not_charge_twice(pay):
    run(SCN, FACTORS, pay, p_miss=0.35)
    r2 = run(SCN, FACTORS, pay, p_miss=0.35)
    assert r2.payment["status"] == "already_held"
    assert len(pay.receipts) == 1


def test_confirm_slot_late_branch(pay):
    run(SCN, FACTORS, pay, p_miss=0.35)
    res = confirm_slot(SCN, FACTORS, pay, paperwork_done=False)
    assert res["status"] == "needs_paperwork"
    res = confirm_slot(SCN, FACTORS, pay, paperwork_done=True)
    assert res["status"] == "approval_requested"
    a = res["approval"]
    assert a.kind == "transport" and a.amount_gbp == 340 and a.owner == OWNER
    assert a.what_for.startswith("Transport: confirms the held slot on NL-417, collection Daventry Tue 20:00")
    assert "ETA Thu 09:00 CET" in a.what_for
    assert a.reason == ("The unit failed its bench test. Confirming the slot costs £340, over your £100 limit. "
                        "It still reaches Monza Thu 09:00 CET, 9 h before the deadline, instead of an emergency "
                        "van at £1,650.")
    assert confirmation_card(SCN, FACTORS, pay) is None
    receipt = pay.decide(a.approval_id, True, by=OWNER, at=SCN.now)
    assert receipt.amount_gbp == 340
    card = confirmation_card(SCN, FACTORS, pay)
    assert card["ref"].startswith("NL-417-") and card["eta"] == "Thu 09:00 CET"
    assert card["collection"].startswith("Daventry Tue 20:00")


def test_release_when_test_passes(pay):
    run(SCN, FACTORS, pay, p_miss=0.35)
    hold = release_hold(SCN, pay)
    assert hold.status == "released"
    assert confirm_slot(SCN, FACTORS, pay, paperwork_done=True)["status"] == "no_active_hold"


def test_impact_numbers(pay):
    r = run(SCN, FACTORS, pay, p_miss=0.35)
    imp = r.impact
    assert imp["headline"] == "1 dedicated cross-border trip avoided"
    assert imp["ours"]["cost_if_late_gbp"] == pytest.approx(400)
    assert imp["usual"]["cost_if_late_gbp"] == pytest.approx(1650)
    assert imp["ours"]["margin_h"] == pytest.approx(9)
    assert imp["arrives_later_than_usual_h"] == pytest.approx(19)
    assert imp["ours"]["co2e_kg"] == pytest.approx(17.2, abs=1)
    assert imp["usual"]["co2e_kg"] == pytest.approx(314.4, abs=1)
