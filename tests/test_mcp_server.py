import asyncio

import pytest

import logistics

try:
    logistics.gbp(1)
except NotImplementedError:
    pytest.skip("waiting for logistics.py", allow_module_level=True)

import mcp_server  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "STATE", tmp_path / "state.json")
    return tmp_path / "state.json"


def tool_names():
    tools = asyncio.run(mcp_server.server.list_tools())
    return {t.name for t in tools}


def test_tools_and_no_approve_tool():
    names = tool_names()
    assert names == {"get_shipment", "check_options", "run_safety_car", "ledger"}
    assert not any(k in n for n in names for k in ("approve", "decide", "confirm"))


def test_check_options_is_a_preview(isolated_state):
    out = mcp_server.check_options(p_miss=0.35)
    assert out["preview_only"] and out["would_pay"] == "booked"
    assert not isolated_state.exists()  # the real account was not touched
    assert mcp_server.check_options(p_miss=0.02)["decision"] == "wait"


def test_run_and_ledger(isolated_state):
    out = mcp_server.run_safety_car(p_miss=0.35)
    assert out["payment"]["status"] == "booked" and out["receipt"]["amount_gbp"] == 60
    again = mcp_server.run_safety_car(p_miss=0.35, fee_rise=True)
    assert again["payment"]["status"] == "already_held" and again["payment"]["amount_gbp"] == 60
    led = mcp_server.ledger()
    assert len(led["receipts"]) == 1 and led["spent_today_gbp"] == 60


def test_fee_rise_waits_for_sarah():
    out = mcp_server.run_safety_car(p_miss=0.35, fee_rise=True)
    assert out["payment"]["status"] == "approval_requested"
    assert "cannot approve" in out["approval"]["message"]
    assert mcp_server.ledger()["pending_approval"]["amount_gbp"] == 120


def test_bad_probability_rejected():
    with pytest.raises(ValueError):
        mcp_server.check_options(p_miss=35)
