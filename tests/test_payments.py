import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from models import Scenario
from payments import Payments

DATA = Path(__file__).resolve().parent.parent / "data"
SCN = Scenario.model_validate(json.loads((DATA / "scenario.json").read_text(encoding="utf-8")))
AT = SCN.now
NORDLINK = "Nordlink Groupage Ltd"
PURPOSE = "backup freight for race week"


@pytest.fixture
def pay(tmp_path):
    return Payments(SCN.policy, SCN.buyer, path=tmp_path / "state.json")


def reserve(pay, amount, offer_id="nordlink", merchant=NORDLINK, purpose=PURPOSE, at=AT):
    return pay.reserve(offer_id=offer_id, merchant=merchant, amount=amount,
                       what_for="Holding fee: reserves 1 pallet space on NL-417 until Tue 18:00 UK",
                       not_included="Transport £340, billed only if the slot is used",
                       cancellation="Non-refundable", purpose=purpose, reason="test reason", at=at)


def hold_and_get(pay):
    res = reserve(pay, 60)
    assert res["status"] == "booked"
    return res["hold"]


def confirm(pay, hold_id, paperwork):
    return pay.confirm(hold_id, amount=340,
                       what_for="Transport: confirms the held slot on NL-417, collection Daventry Tue 20:00, "
                                "ETA Thu 09:00 CET",
                       paperwork_done=paperwork, purpose=PURPOSE, reason="unit failed its bench test", at=AT)


def test_60_is_booked_with_receipt(pay):
    res = reserve(pay, 60)
    assert res["status"] == "booked"
    r = res["receipt"]
    assert r.amount_gbp == 60 and r.payee == NORDLINK and r.simulated
    assert "4242" in r.card and "never sees" in r.card
    assert "Within Sarah Clarke's policy" in r.authorisation
    assert r.not_included.startswith("Transport £340")
    assert res["hold"].status == "held" and res["hold"].receipt_id == r.receipt_id


def test_120_requests_approval(pay):
    res = reserve(pay, 120)
    assert res["status"] == "approval_requested"
    a = res["approval"]
    assert a.amount_gbp == 120 and a.owner == "Sarah Clarke" and a.status == "pending"
    assert any("above the £100 per-hold limit" in r for r in a.policy_reasons)
    assert a.reason == "test reason"
    assert pay.receipts == []


def test_owner_approves_120(pay):
    a = reserve(pay, 120)["approval"]
    r = pay.decide(a.approval_id, True, by="Sarah Clarke", at=AT)
    assert r.amount_gbp == 120
    assert r.authorisation == "Approved by Sarah Clarke (Head of Logistics) because it was over the £100 limit"
    assert pay.active_hold("nordlink").receipt_id == r.receipt_id
    assert pay.pending_approval() is None


@pytest.mark.parametrize("who", ["safety-car-01", "Dan (SwiftVan Express)", "sarah clarke", ""])
def test_only_owner_can_decide(pay, who):
    a = reserve(pay, 120)["approval"]
    with pytest.raises(PermissionError):
        pay.decide(a.approval_id, True, by=who, at=AT)
    assert pay.receipts == []
    assert pay.pending_approval().approval_id == a.approval_id
    assert pay.ledger[-1].kind == "blocked"


def test_decline_no_charge(pay):
    a = reserve(pay, 120)["approval"]
    assert pay.decide(a.approval_id, False, by="Sarah Clarke", at=AT) is None
    assert pay.receipts == [] and pay.holds == []
    assert pay.approvals[0].status == "declined"


def test_approve_twice_one_receipt(pay):
    a = reserve(pay, 120)["approval"]
    assert pay.decide(a.approval_id, True, by="Sarah Clarke", at=AT) is not None
    assert pay.decide(a.approval_id, True, by="Sarah Clarke", at=AT) is None
    assert len(pay.receipts) == 1


def test_confirm_needs_paperwork(pay):
    hold = hold_and_get(pay)
    res = confirm(pay, hold.hold_id, paperwork=False)
    assert res["status"] == "needs_paperwork"
    assert len(pay.receipts) == 1


def test_confirm_transport_approval_flow(pay):
    hold = hold_and_get(pay)
    res = confirm(pay, hold.hold_id, paperwork=True)
    assert res["status"] == "approval_requested"
    a = res["approval"]
    assert a.kind == "transport" and a.amount_gbp == 340 and a.hold_id == hold.hold_id
    # Clicking confirm again does not create a second request.
    again = confirm(pay, hold.hold_id, paperwork=True)
    assert again["status"] == "approval_requested" and again["approval"].approval_id == a.approval_id
    assert len(pay.approvals) == 1

    r = pay.decide(a.approval_id, True, by="Sarah Clarke", at=AT)
    assert r.amount_gbp == 340 and r.kind == "transport"
    assert "Approved by Sarah Clarke" in r.authorisation
    h = pay.holds[0]
    assert h.status == "used"
    assert h.confirmation_ref and h.confirmation_ref.startswith("NL-417-")
    assert pay.transport_receipt(hold.hold_id).receipt_id == r.receipt_id
    assert pay.receipt_for(hold.hold_id).amount_gbp == 60


def test_unknown_merchant_denied(pay):
    res = reserve(pay, 60, merchant="Shady Freight Co")
    assert res["status"] == "denied"
    assert "not an approved merchant" in res["decision"].reasons[0]
    assert pay.receipts == []


def test_wrong_purpose_denied(pay):
    assert reserve(pay, 60, purpose="team hospitality")["status"] == "denied"


def test_second_reserve_does_not_charge_twice(pay):
    first = reserve(pay, 60)
    second = reserve(pay, 60)
    assert second["status"] == "already_held"
    assert second["hold"].hold_id == first["hold"].hold_id
    assert len(pay.receipts) == 1


def test_second_reserve_while_pending_returns_pending(pay):
    a = reserve(pay, 120)["approval"]
    again = reserve(pay, 120)
    assert again["status"] == "approval_requested" and again["approval"].approval_id == a.approval_id
    assert len(pay.approvals) == 1


def test_release(pay):
    hold = hold_and_get(pay)
    assert pay.release(hold.hold_id, at=AT).status == "released"
    assert pay.active_hold("nordlink") is None
    assert pay.ledger[-1].kind == "release"
    assert confirm(pay, hold.hold_id, paperwork=True)["status"] == "not_active"


def test_daily_limit_needs_approval(pay):
    for i in range(3):  # 3 x £90 = £270 of the £300 daily limit
        assert reserve(pay, 90, offer_id=f"o{i}")["status"] == "booked"
    res = reserve(pay, 90, offer_id="o4")
    assert res["status"] == "approval_requested"
    assert any("daily limit" in r for r in res["approval"].policy_reasons)
    # Next day the daily budget is fresh.
    assert reserve(pay, 90, offer_id="o5", at=AT + timedelta(days=1))["status"] == "booked"


def test_every_action_is_on_the_ledger(pay):
    hold = hold_and_get(pay)
    a = confirm(pay, hold.hold_id, paperwork=True)["approval"]
    pay.decide(a.approval_id, True, by="Sarah Clarke", at=AT)
    kinds = [e.kind for e in pay.ledger]
    for k in ["policy_check", "charge", "approval_requested", "approved", "confirmed"]:
        assert k in kinds
    pay.check_policy(NORDLINK, 10, PURPOSE, AT)
    assert pay.ledger[-1].kind == "policy_check"


def test_state_survives_reload(tmp_path):
    path = tmp_path / "state.json"
    p1 = Payments(SCN.policy, SCN.buyer, path=path)
    a = reserve(p1, 120)["approval"]
    # The phone screen is a different process: it sees the same pending approval.
    p2 = Payments(SCN.policy, SCN.buyer, path=path)
    assert p2.pending_approval().approval_id == a.approval_id
    p2.decide(a.approval_id, True, by="Sarah Clarke", at=AT)
    assert p1.active_hold("nordlink") is not None
    assert len(p1.receipts) == 1
    assert isinstance(Payments(SCN.policy, SCN.buyer, path=path).receipts[0].issued_at, datetime)


def test_reset(pay):
    hold_and_get(pay)
    pay.reset()
    assert pay.holds == [] and pay.receipts == [] and pay.ledger == []
