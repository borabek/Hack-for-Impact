"""The 14:00 gate as one test: drive app.py through the CLAUDE.md section 2 demo path, exactly as on stage,
with two sessions: the laptop (Supplier ops) and C's phone (Buyer phone view). Owner: Person A (integration).

    pytest tests/test_demo_path.py -q

Any existing data/state.json is backed up first and restored afterwards, so this never disturbs a live demo.
"""
import json
import shutil
from pathlib import Path

import pytest

import logistics

try:
    logistics.gbp(1)
except NotImplementedError:
    pytest.skip("waiting for logistics.py", allow_module_level=True)

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
STATE = ROOT / "data" / "state.json"
TIMEOUT = 90


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    for k in ("LLM_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)  # the gate runs with no key, like the stage
    backup = tmp_path / "state_backup.json"
    if STATE.exists():
        shutil.copy2(STATE, backup)
    STATE.unlink(missing_ok=True)
    yield
    STATE.unlink(missing_ok=True)
    if backup.exists():
        shutil.copy2(backup, STATE)


def state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else \
        {"holds": [], "receipts": [], "approvals": [], "ledger": []}


def errors(at):
    return [e.message for e in at.exception] + [e.value for e in at.error]


def button(at, text):
    matches = [b for b in at.button if text in b.label]
    assert matches, f"no button containing {text!r}; buttons: {[b.label for b in at.button]}"
    return matches[0]


def page_text(at):
    return " ".join(str(m.value) for m in at.markdown)


def session(view=None):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not errors(at), errors(at)
    if view:
        at.radio[0].set_value(view).run()
        assert not errors(at), errors(at)
    return at


def test_full_demo_path_laptop_and_phone():
    laptop = session()
    shown = page_text(laptop) + " ".join(str(c.value) for c in laptop.caption)
    assert "stand-ins" not in shown, "app fell back to stand-ins: agent.py/payments.py failed to load"
    assert "Person A" not in shown, "internal team text is visible to judges"
    button(laptop, "Reset demo").click().run()

    # Step 4: £60 within policy, receipt.
    button(laptop, "Run the Safety Car agent").click().run()
    assert not errors(laptop), errors(laptop)
    s = state()
    assert [r["amount_gbp"] for r in s["receipts"]] == [60]
    assert "Booked a £60 hold" in page_text(laptop)

    # Step 5: replay £120 -> approval on the phone, a separate session.
    button(laptop, "Replay: fee rises to £120").click().run()
    assert not errors(laptop), errors(laptop)
    s = state()
    pending = [a for a in s["approvals"] if a["status"] == "pending"]
    assert s["receipts"] == [] and len(pending) == 1 and pending[0]["amount_gbp"] == 120
    phone = session("Buyer phone")
    assert "approval needed" in page_text(phone).lower() and "£120" in page_text(phone)
    button(phone, "Approve").click().run()
    assert not errors(phone), errors(phone)
    assert any(r["amount_gbp"] == 120 and "Approved by Sarah Clarke" in r["authorisation"]
               for r in state()["receipts"])
    laptop.run()
    assert "£120 hold" in page_text(laptop)

    # Step 6: late branch. Paperwork blocks, then £340 needs Sarah, then the carrier confirms.
    phone.run()
    button(phone, "Bench test failed").click().run()
    assert not any(a.get("kind") == "transport" for a in state()["approvals"])
    next(c for c in phone.checkbox if "Paperwork" in c.label).check().run()
    button(phone, "Bench test failed").click().run()
    transport = [a for a in state()["approvals"] if a.get("kind") == "transport" and a["status"] == "pending"]
    assert len(transport) == 1 and transport[0]["amount_gbp"] == 340
    button(phone, "Approve").click().run()
    used = [h for h in state()["holds"] if h["status"] == "used"]
    assert used and used[0]["confirmation_ref"].startswith("NL-417-")
    assert "carrier confirmation" in page_text(phone).lower()
    assert not errors(phone), errors(phone)

    # Step 7: impact card.
    laptop.run()
    assert not errors(laptop), errors(laptop)
    text = page_text(laptop)
    for needle in ("1 dedicated cross-border trip avoided", "£460", "£1,650"):
        assert needle in text, needle

    for view in ("Carrier", "Ledger", "Pitch"):
        laptop.radio[0].set_value(view).run()
        assert not errors(laptop), (view, errors(laptop))


def test_release_branch_and_low_risk():
    laptop = session()
    button(laptop, "Reset demo").click().run()
    button(laptop, "Run the Safety Car agent").click().run()
    phone = session("Buyer phone")
    button(phone, "Bench test passed").click().run()
    assert state()["holds"][0]["status"] == "released"

    button(laptop, "Reset demo").click().run()
    laptop.slider[0].set_value(0.02).run()
    button(laptop, "Run the Safety Car agent").click().run()
    assert not errors(laptop), errors(laptop)
    assert state()["receipts"] == []
