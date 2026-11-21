"""app.py: Safety Car demo UI (Person B). Run: streamlit run app.py

One screen for the demo: supplier ops on the left, "Sarah's phone" on the right.
Side effects (payments) happen only on button clicks. State lives in st.session_state
and in the payments object (data/state.json), which the phone view shares.

Backend: uses Person A's agent.py / payments.py when they are implemented. Until then it falls
back to the stand-ins in standins/ (and says so in the sidebar), so the UI can be built and tested early.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))
try:
    import models  # noqa: F401  (Person A's file)
except ImportError:  # A has not pushed yet
    sys.path.insert(0, str(ROOT / "standins"))
    import models  # noqa: F401

import logistics as lg  # noqa: E402

st.set_page_config(page_title="Safety Car", page_icon="🚨", layout="wide")

# Streamlit renamed use_container_width=True to width="stretch": support both.
import inspect  # noqa: E402

STRETCH = {"width": "stretch"} if "width" in inspect.signature(st.button).parameters else {"use_container_width": True}

# --------------------------------------------------------------------------- backend wiring


def _load_standin(name: str):
    spec = importlib.util.spec_from_file_location(f"standin_{name}", ROOT / "standins" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"standin_{name}"] = mod  # dataclasses need the module registered
    spec.loader.exec_module(mod)
    return mod


@st.cache_resource(show_spinner=False)
def load_backend():
    """(agent_module, payments_module, label). Real modules if they work, else the stand-ins."""
    scn = json.loads((DATA / "scenario.json").read_text(encoding="utf-8"))
    try:
        import agent as real_agent  # noqa: WPS433
        import payments as real_payments  # noqa: WPS433

        for mod in (real_agent, real_payments):  # never mistake the stand-ins for A's files
            if Path(mod.__file__).resolve().parent != ROOT:
                raise ImportError("not Person A's module")

        m = models
        S = m.Scenario.model_validate(scn)
        factors = json.loads((DATA / "factors.json").read_text(encoding="utf-8"))
        probe = real_payments.Payments(S.policy, S.buyer, str(Path(tempfile.mkdtemp()) / "probe.json"))
        real_agent.run(S, factors, probe, p_miss=0.35, fee_rise=False, use_llm=False)
        return real_agent, real_payments, "Person A's agent.py and payments.py"
    except Exception as exc:  # NotImplementedError, ImportError, wrong signature, anything
        print(f"[app] using stand-ins ({type(exc).__name__}: {exc})", file=sys.stderr)
        return _load_standin("agent"), _load_standin("payments"), "stand-ins (A's modules are not ready yet)"


AGENT, PAYMENTS_MOD, BACKEND_LABEL = load_backend()


@st.cache_data(show_spinner=False)
def load_data():
    scn = models.Scenario.model_validate_json((DATA / "scenario.json").read_text(encoding="utf-8"))
    factors = json.loads((DATA / "factors.json").read_text(encoding="utf-8"))
    msgs = {p.name: p.read_text(encoding="utf-8") for p in sorted((DATA / "carriers").glob("*.txt"))}
    return scn, factors, msgs


SCN, FACTORS, MESSAGES = load_data()
SHIP, POLICY = SCN.shipment, SCN.policy
NOW = SCN.now


def get_payments():
    if "pay" not in st.session_state:
        st.session_state.pay = PAYMENTS_MOD.Payments(POLICY, SCN.buyer, str(DATA / "state.json"))
    return st.session_state.pay


PAY = get_payments()

# --------------------------------------------------------------------------- styling (projector-friendly)

RED = "#E10600"
st.markdown(
    f"""
<style>
.block-container {{padding-top: 1.2rem; padding-bottom: 1rem;}}
.pill {{display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;color:#fff;}}
.pill.bookable_now{{background:#1a7f37}} .pill.fallback{{background:#57606a}}
.pill.conditional{{background:#bf8700}} .pill.blocked{{background:{RED}}}
.big {{font-size:2.1rem;font-weight:800;line-height:1.1;}}
.bignum {{font-size:1.9rem;font-weight:800;line-height:1.05;}}
.sub {{color:#57606a;font-size:0.85rem;}}
.card {{border:1px solid #d0d7de;border-radius:12px;padding:14px 16px;margin-bottom:10px;background:#fff;color:#1f2328;}}
.card.receipt {{border:2px solid #1a7f37;}}
.card.approval {{border:3px solid {RED};background:#fff5f5;}}
.card.confirm {{border:2px solid #0969da;background:#f2f8ff;}}
.phone {{border:6px solid #1f2328;border-radius:28px;padding:10px 12px;background:#f6f8fa;color:#1f2328;}}
.headline {{font-size:1.5rem;font-weight:800;color:#1a7f37;}}
.warn {{color:#9a6700;}}
.mono {{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.85rem;}}
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- tiny helpers


def pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def kg(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:,.1f} kg"


def step_parts(step: Any):
    """Agent steps may be (icon, title, detail) tuples, dicts or objects."""
    if isinstance(step, (tuple, list)):
        return (list(step) + ["", "", ""])[:3]
    if isinstance(step, dict):
        return step.get("icon", ""), step.get("title", ""), step.get("detail", "")
    return getattr(step, "icon", ""), getattr(step, "title", ""), getattr(step, "detail", "")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("’", "'").replace("–", "-").replace("—", "-")).strip()


def checks_for(run: Any, offer: Any) -> List[Any]:
    """Quote checks for an offer: from the agent run if it has them, else computed here."""
    c = getattr(run, "checks", None)
    if isinstance(c, dict):
        for key in (offer.offer_id, offer.source_file):
            if key in c and c[key]:
                return list(c[key])
    out = []
    body = norm(MESSAGES.get(offer.source_file, ""))
    for f, q in offer.evidence.items():
        ok = norm(q) in body
        out.append(models.QuoteCheck(field=f, quote=q, verified=ok, score=100.0 if ok else 0.0))
    return out


def state_lists():
    return (
        list(getattr(PAY, "ledger", [])),
        list(getattr(PAY, "holds", [])),
        list(getattr(PAY, "receipts", [])),
        list(getattr(PAY, "approvals", [])),
    )


def option_of(run: Any, attr: str) -> Any:
    """run.recommended / run.baseline as an OptionEval. A's agent stores the offer_id; the stand-in stores the eval."""
    val = getattr(run, attr, None) if run else None
    if isinstance(val, str):
        return next((e for e in getattr(run, "options", []) if e.offer.offer_id == val), None)
    return val


def offers_of(run: Any) -> List[Any]:
    """run.offers as a list. A's agent keeps a dict offer_id -> Offer; the stand-in keeps a list."""
    offers = getattr(run, "offers", None) or []
    return list(offers.values()) if isinstance(offers, dict) else list(offers)


def current_hold_fee(run: Any) -> float:
    """The hold fee actually in force: the recommended offer's fee, else 60/120 by the toggle."""
    rec = option_of(run, "recommended")
    if rec is not None and rec.offer.hold_fee_gbp:
        return float(rec.offer.hold_fee_gbp)
    return 120.0 if st.session_state.get("fee_rise") else 60.0


# --------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("### 🚨 Safety Car")
    view = st.radio("View", ["Supplier ops", "Buyer phone", "Carrier", "Ledger", "Pitch"], label_visibility="collapsed")
    p_miss = st.slider("Chance the unit misses the truck", 0.0, 1.0, float(SHIP.p_miss_main_truck), 0.01, format="%.2f")
    use_llm = st.toggle("Live AI extraction", value=False, disabled=True, help="Replayed extraction is the default so the demo can't fail on stage.")
    st.session_state.setdefault("fee_rise", False)

    # decision preview: makes no payment
    try:
        ev0 = lg.evaluate_all(AGENT.gather_offers(False)[0], SCN, FACTORS, p_miss) if hasattr(AGENT, "gather_offers") else None
    except Exception:
        ev0 = None
    if ev0 is None:
        raw = json.loads((DATA / "expected_offers.json").read_text(encoding="utf-8"))
        offers0 = [models.Offer(offer_id=f.split("_")[0], source_file=f, **v) for f, v in raw.items() if f != "nordlink_update.txt"]
        ev0 = lg.evaluate_all(offers0, SCN, FACTORS, p_miss)
    _by0 = {e.offer.offer_id: e for e in ev0}
    _nl, _base = _by0.get("nordlink"), _by0.get(SCN.baseline_offer_id)
    _hold_now = 120.0 if st.session_state.fee_rise else 60.0
    if _nl and _base:
        text, _ = lg.decision_preview(_hold_now, _nl.price_gbp, _base.price_gbp, p_miss)
        st.info(text)

    if st.button("Reset demo", **STRETCH):
        PAY.reset()
        for k in ("run", "fee_rise", "confirmed"):
            st.session_state.pop(k, None)
        st.rerun()
    st.caption(f"Backend: {BACKEND_LABEL}")
    st.caption("FICTIONAL SCENARIO. Prices are illustrative unless sourced.")

# --------------------------------------------------------------------------- actions


def do_run(fee_rise: bool) -> None:
    st.session_state.fee_rise = fee_rise
    st.session_state.run = AGENT.run(SCN, FACTORS, PAY, p_miss=p_miss, fee_rise=fee_rise, use_llm=False)


def do_decide(approval_id: str, approve: bool) -> None:
    try:
        PAY.decide(approval_id, approve, POLICY.owner, NOW)
    except PermissionError as exc:
        st.error(str(exc))


def do_confirm(paperwork: bool) -> Dict[str, Any]:
    res = AGENT.confirm_slot(SCN, FACTORS, PAY, paperwork_done=paperwork)
    st.session_state.confirmed = res
    return res


# --------------------------------------------------------------------------- phone panel (used in two views)


def phone_panel(run: Any, key: str = "") -> None:
    ledger, holds, receipts, approvals = state_lists()
    pending = next((a for a in approvals if a.status == "pending"), None)
    st.markdown("#### 📱 Sarah's phone")
    st.caption(f"{SCN.buyer.approver}, {SCN.buyer.approver_role}, {SCN.buyer.company}")
    st.markdown('<div class="phone">', unsafe_allow_html=True)

    if pending:
        kind = "Transport charge" if pending.kind == "transport" else "Holding fee"
        st.markdown(
            f"""<div class="card approval"><div class="sub">APPROVAL NEEDED · {kind}</div>
<div class="big">{lg.gbp(pending.amount_gbp)}</div>
<b>{pending.merchant}</b><br>{pending.what_for}<br><br>
<b>Why the agent asks:</b> {'; '.join(pending.policy_reasons) or 'over policy'}.<br>
<span class="sub">{pending.reason}</span></div>""",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        c1.button("✅ Approve", key=f"approve{key}", type="primary", **STRETCH,
                  on_click=do_decide, args=(pending.approval_id, True))
        c2.button("Decline", key=f"decline{key}", **STRETCH,
                  on_click=do_decide, args=(pending.approval_id, False))
    else:
        last = receipts[-1] if receipts else None
        if last:
            st.markdown(receipt_html(last), unsafe_allow_html=True)
        else:
            st.markdown('<div class="card">No payments or approvals yet.<br><span class="sub">Run the agent.</span></div>', unsafe_allow_html=True)

    with st.expander("Standing authorisation (spend policy)"):
        st.write(
            f"Agent **{POLICY.agent_id}** may spend up to **£{POLICY.per_call_limit_gbp:g}** per hold, "
            f"£{POLICY.daily_limit_gbp:g} a day, £{POLICY.monthly_limit_gbp:g} a month, only with: "
            f"{', '.join(POLICY.allowed_merchants)}. Purpose: *{POLICY.purpose}*. "
            f"Anything over a limit comes to {POLICY.owner}. The agent never sees the card and cannot approve its own request."
        )

    active = next((h for h in holds if h.status == "held"), None)
    done = next((h for h in holds if h.status == "used"), None)
    if active:
        st.markdown(f"**Hold in place:** {active.merchant}, {lg.gbp(active.amount_gbp)}")
        paperwork = st.checkbox("Paperwork done (ATA Carnet / commercial invoice)", key=f"paper{key}")
        b1, b2 = st.columns(2)
        if b1.button("Bench test passed → release the hold", key=f"rel{key}", **STRETCH):
            PAY.release(active.hold_id, NOW)
            st.rerun()
        if b2.button("Bench test failed → confirm the slot", key=f"conf{key}", type="primary", **STRETCH):
            res = do_confirm(paperwork)
            st.session_state.paperwork_warn = res.get("status") == "needs_paperwork"
            st.rerun()
        if st.session_state.get("paperwork_warn") and not paperwork:
            st.warning("Paperwork first: tick the box once the ATA Carnet or commercial invoice is done.")
    if done and done.confirmation_ref:
        st.markdown(
            f"""<div class="card confirm"><div class="sub">CARRIER CONFIRMATION</div>
<div class="big">{done.confirmation_ref}</div>
{done.merchant} · trunk NL-417<br>Collection <b>Daventry Tue 20:00</b> · ETA <b>Monza Thu 09:00 CET</b><br>
<span class="sub">Simulated confirmation.</span></div>""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def receipt_html(r: Any) -> str:
    not_inc = f"<br><b>Not included:</b> {r.not_included}" if r.not_included else ""
    return f"""<div class="card receipt"><div class="sub">RECEIPT {r.receipt_id} · SIMULATED</div>
<div class="big">{lg.gbp(r.amount_gbp)}</div>
<b>Paid to:</b> {r.payee}<br><b>For:</b> {r.paid_for}{not_inc}<br>
<b>Authorised:</b> {r.authorisation}<br><span class="sub">{r.card}</span></div>"""


# --------------------------------------------------------------------------- ops view pieces


def status_pill(s: str) -> str:
    return f'<span class="pill {s}">{s.replace("_", " ")}</span>'


def options_table(run: Any) -> None:
    rows = []
    for e in run.options:
        hold = e.offer.hold_fee_gbp
        rows.append(
            {
                "Carrier": e.offer.carrier,
                "Type": (e.offer.mode or "").replace("_", " "),
                "Status": e.status.replace("_", " "),
                "Hold now": lg.gbp(hold) if hold else "none",
                "Cost if used": lg.gbp(e.cost_if_used_gbp, 0),
                "Expected cost": lg.gbp(e.expected_cost_gbp, 0),
                "Arrives": lg.fmt(e.arrival),
                "Spare": lg.hours_text(e.margin_h),
                "CO2e": kg(e.co2e_kg),
                "Watch-outs": " | ".join(e.issues + [n for n in e.notes][:2]) or "none",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, **STRETCH)


def pit_window_chart(run: Any) -> None:
    rows = []
    for e in run.options:
        if e.arrival is None:
            continue
        start = e.departure or (e.arrival - pd.Timedelta(hours=1))
        rows.append(
            {
                "Option": e.offer.carrier,
                "start": pd.Timestamp(start).tz_convert("UTC").tz_localize(None),
                "end": pd.Timestamp(e.arrival).tz_convert("UTC").tz_localize(None),
                "Status": e.status.replace("_", " "),
            }
        )
    if not rows:
        return
    df = pd.DataFrame(rows)
    dl = pd.Timestamp(SHIP.deadline).tz_convert("UTC").tz_localize(None)
    colour = alt.Scale(domain=["bookable now", "fallback", "conditional", "blocked"], range=["#1a7f37", "#57606a", "#bf8700", RED])
    bars = alt.Chart(df).mark_bar(size=22).encode(
        y=alt.Y("Option:N", sort=None, title=None),
        x=alt.X("start:T", title="Time (UTC)"),
        x2="end:T",
        color=alt.Color("Status:N", scale=colour, legend=alt.Legend(orient="bottom")),
        tooltip=["Option", "Status", "start", "end"],
    )
    rule = alt.Chart(pd.DataFrame({"d": [dl]})).mark_rule(color=RED, strokeDash=[6, 4], size=3).encode(x="d:T")
    label = alt.Chart(pd.DataFrame({"d": [dl], "t": [f"Deadline {lg.fmt(SHIP.deadline)}"]})).mark_text(
        align="right", dx=-4, dy=-8, color=RED, fontWeight="bold"
    ).encode(x="d:T", y=alt.value(0), text="t:N")
    st.altair_chart((bars + rule + label).properties(height=190), **STRETCH)


def impact_card(run: Any) -> None:
    rec, base = option_of(run, "recommended"), option_of(run, "baseline")
    st.subheader("Impact: usual plan vs Safety Car")
    if rec is None or base is None:
        st.info("Run the agent to see the comparison. (If the chance of a miss is below the break-even, it waits and buys nothing.)")
        return
    hold = current_hold_fee(run)
    imp = lg.impact(rec, base, hold, p_miss)
    scen = f"{lg.gbp(hold)} hold" + (", after the fee rise" if hold > POLICY.per_call_limit_gbp else "")
    approved = any(a.status == "approved" for a in state_lists()[3])
    if hold > POLICY.per_call_limit_gbp and approved:
        scen += ", approved by Sarah"
    st.caption(f"Scenario shown: **{scen}**, {p_miss:.0%} chance of a miss. Case: the unit fails its bench test.")
    if imp["trips_avoided"]:
        st.markdown('<div class="headline">1 dedicated cross-border trip avoided</div>', unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f'<div class="sub">Cost if late</div><div class="bignum">{lg.gbp(imp["cost_if_late_ours"])}</div><div class="sub">vs {lg.gbp(imp["cost_if_late_usual"])} usual</div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="sub">Arrives</div><div class="bignum">{lg.fmt(imp["arrival_ours"])}</div><div class="sub">{imp["margin_ours_h"]:g} h before the deadline</div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="sub">CO2e (modelled)</div><div class="bignum">≈{imp["co2e_ours"]:.0f} kg</div><div class="sub">vs ≈{imp["co2e_usual"]:.0f} kg usual</div>', unsafe_allow_html=True)
    m4.markdown(f'<div class="sub">Dedicated vehicle-km</div><div class="bignum">{imp["km_ours"]:g}</div><div class="sub">vs {imp["km_usual"]:g} usual</div>', unsafe_allow_html=True)

    table = pd.DataFrame(
        {
            "": ["Journey", "Cost if the unit is late", "Cost if it makes the truck", "Expected cost", "Arrival", "Spare time", "Dedicated km", "CO2e (modelled)"],
            "Usual plan: wait, then emergency van": [
                f"{base.offer.carrier} dedicated van", lg.gbp(imp["cost_if_late_usual"]), "£0", lg.gbp(imp["expected_usual"]),
                lg.fmt(imp["arrival_usual"]), lg.hours_text(imp["margin_usual_h"]), f'{imp["km_usual"]:g}', kg(imp["co2e_usual"]),
            ],
            "Safety Car: hold now": [
                f"{rec.offer.carrier} pallet space on a truck already going", lg.gbp(imp["cost_if_late_ours"]), lg.gbp(hold), lg.gbp(imp["expected_ours"]),
                lg.fmt(imp["arrival_ours"]), lg.hours_text(imp["margin_ours_h"]), f'{imp["km_ours"]:g}', kg(imp["co2e_ours"]),
            ],
        }
    )
    st.dataframe(table, hide_index=True, **STRETCH)
    be = imp["breakeven"]
    st.markdown(
        f"**Expected cost at {p_miss:.0%}:** {lg.gbp(imp['expected_ours'])} with the hold vs {lg.gbp(imp['expected_usual'])} waiting. "
        f"The hold pays for itself above a **{pct(be)}** chance of a miss."
    )
    st.markdown(
        f"The van would arrive **{imp['later_by_h']:.0f} h earlier**. We still arrive **{imp['margin_ours_h']:g} h before** the deadline: "
        "paying for speed nobody needs is the waste we remove."
    )
    with st.expander("How CO2e was worked out (boundary and sources)", expanded=False):
        st.write("**Modelled estimate, not a measurement.** UK Government GHG Conversion Factors 2025 (see the sources table).")
        st.write(f"**Safety Car:** {rec.co2e_note}")
        st.write(f"**Usual plan:** {base.co2e_note}")
        st.write("Boundary: the first mile to the hub is included; the van's empty return trip is excluded, which flatters the usual plan.")
        if rec.offer.emissions_claim:
            st.warning(
                f"Carrier claim, unverified: \"{rec.offer.emissions_claim}\". It is per pallet at an 80% load factor, "
                "so it measures something different. We do not compare it with our number."
            )


def what_the_ai_read(run: Any) -> None:
    st.subheader("What the AI read")
    mode = getattr(run, "mode", None) or getattr(run, "extraction", None)
    st.caption("Replayed extraction (hand-checked answers; no network)." if mode in (None, "replayed") else f"Extraction: {mode}")
    for o in offers_of(run):
        checks = checks_for(run, o)
        ok = sum(1 for c in checks if c.verified)
        auto_open = o.offer_id == "aerodash"
        with st.expander(f"{o.carrier} · {ok}/{len(checks)} quotes verified" + (" · small print caught" if auto_open else ""), expanded=auto_open):
            text = MESSAGES.get(o.source_file, "")
            hl = o.evidence.get("max_weight_kg_per_piece") if auto_open else None
            if hl and hl in text:
                st.markdown(
                    "**Original message** (highlighted: the line that rules this option out)\n\n```\n"
                    + text.replace(hl, f">>> {hl} <<<")
                    + "\n```"
                )
            else:
                st.text_area("Original message", text, height=170, disabled=True, key=f"msg_{o.offer_id}_{o.source_file}")
            rows = []
            for c in checks:
                rows.append({"Field": c.field, "Value": str(getattr(o, c.field, "")), "Quote": c.quote, "Check": "✅" if c.verified else "⚠️"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, **STRETCH)
            if o.limitations:
                st.markdown("**Small print:** " + " · ".join(o.limitations))
            for f in o.flags:
                st.warning(f"🛡️ {f}")


def assumptions_table() -> None:
    st.subheader("Assumptions and sources")
    rows = []
    for section in ("emission_factors", "distances_km", "assumptions"):
        for key, v in FACTORS.get(section, {}).items():
            rows.append(
                {
                    "Item": v.get("label", key),
                    "Value": f'{v["value"]:g} {v.get("unit", "")}'.strip(),
                    "Source": v.get("source", ""),
                    "Status": "verified" if v.get("verified") else "⚠️ illustrative / approximate",
                }
            )
    st.dataframe(pd.DataFrame(rows), hide_index=True, **STRETCH)


# --------------------------------------------------------------------------- views


def ops_view() -> None:
    run = st.session_state.get("run")
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.markdown("## 🚨 Safety Car")
        st.markdown("**£60 on Monday beats £1,650 on Wednesday.** An agent that buys the backup before you know you need it, inside rules the boss set once.")
        st.caption(SCN.label)
        a, b, c, d = st.columns(4)
        a.metric("Deadline", lg.fmt(SHIP.deadline))
        b.metric("Main truck leaves", lg.fmt(SHIP.main_truck_departure))
        c.metric("Bench-test result", lg.fmt(SHIP.bench_test_result_at))
        d.metric("Chance of a miss", f"{p_miss:.0%}")

        r1, r2 = st.columns(2)
        r1.button("▶ Run the Safety Car agent", type="primary", **STRETCH,
                  on_click=lambda: (PAY.reset(), do_run(False)))
        r2.button("Replay: fee rises to £120 before booking", **STRETCH,
                  on_click=lambda: (PAY.reset(), do_run(True)))

        if run is None:
            st.info("Press **Run the Safety Car agent**. It reads the carrier messages, checks every option against the deadline and the small print, and decides.")
            return

        st.markdown("### Agent log")
        for s in run.steps:
            icon, title, detail = step_parts(s)
            st.markdown(f"{icon} **{title}**" + (f"<br><span class='sub'>{detail}</span>" if detail else ""), unsafe_allow_html=True)
        if getattr(run, "explanation", ""):
            st.markdown(f'<div class="card">{run.explanation}</div>', unsafe_allow_html=True)

        _, _, receipts, approvals = state_lists()
        pend = next((a for a in approvals if a.status == "pending"), None)
        if pend:
            st.warning(f"⏳ Waiting for {POLICY.owner}'s approval of {lg.gbp(pend.amount_gbp)} → approve on the phone.")
        elif receipts:
            st.markdown(receipt_html(receipts[-1]), unsafe_allow_html=True)

        st.markdown("### Options")
        options_table(run)
        st.markdown("### Pit window")
        pit_window_chart(run)
        impact_card(run)
        what_the_ai_read(run)
        assumptions_table()
    with right:
        phone_panel(run, key="_ops")


def phone_view() -> None:
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        phone_panel(st.session_state.get("run"), key="_phone")
        if st.button("↻ Refresh"):
            st.rerun()


def carrier_view() -> None:
    st.markdown("## Carrier view: Nordlink Groupage")
    st.caption("The same money, seen as revenue on space that would otherwise travel empty. Built from the payments state.")
    _, holds, receipts, _ = state_lists()
    mine = [h for h in holds if h.offer_id == "nordlink"]
    sold = list(mine)
    hold_receipts = {h.receipt_id for h in mine if h.receipt_id}
    mine_ids = {h.hold_id for h in mine}
    fees = sum(r.amount_gbp for r in receipts if r.receipt_id in hold_receipts)
    transport = sum(r.amount_gbp for r in receipts if r.hold_id in mine_ids and r.receipt_id not in hold_receipts)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trunk", "NL-417")
    c2.metric("Spare pallet spaces sold as holds", len(sold))
    c3.metric("Holding fees earned", lg.gbp(fees))
    c4.metric("Transport confirmed", lg.gbp(transport))
    st.write("Trunk NL-417, Daventry hub to Monza paddock, departs Tue 21:00 UK, ETA Thu 09:00 CET. One spare pallet space, held for the buyer until Tue 18:00.")
    if not mine:
        st.info("No holds sold yet. Run the agent on the Supplier ops view.")
    for h in mine:
        st.markdown(
            f"- **{h.hold_id}**: {lg.gbp(h.amount_gbp)} · status **{h.status}**"
            + (f" · confirmation sent: **{h.confirmation_ref}**" if h.confirmation_ref else "")
            + (" · fee kept even though the slot was released" if h.status == "released" else "")
        )


def ledger_view() -> None:
    st.markdown("## Ledger")
    ledger, holds, receipts, approvals = state_lists()
    if not ledger:
        st.info("Nothing on the ledger yet.")
    else:
        st.dataframe(
            pd.DataFrame([{"At": x.at, "Kind": x.kind, "Detail": x.detail, "£": x.amount_gbp} for x in ledger]),
            hide_index=True, **STRETCH,
        )
    st.markdown("### Holds")
    st.dataframe(pd.DataFrame([h.model_dump(mode="json") for h in holds]) if holds else pd.DataFrame(), hide_index=True, **STRETCH)
    st.markdown("### Approvals")
    st.dataframe(pd.DataFrame([a.model_dump(mode="json") for a in approvals]) if approvals else pd.DataFrame(), hide_index=True, **STRETCH)


def pitch_view() -> None:
    run = st.session_state.get("run")
    st.markdown("## Pitch")
    st.markdown("### Opening: the buyer and the shipment at risk")
    st.markdown(
        f"""<div class="card"><div class="big">{SCN.buyer.company}</div>
Milton Keynes supplier. The truck to Monza leaves <b>{lg.fmt(SHIP.main_truck_departure)}</b>. One timing unit is still on the bench:
<b>{SHIP.p_miss_main_truck:.0%}</b> chance it misses the truck. The garage needs it by <b>{lg.fmt(SHIP.deadline)}</b>.<br>
Today: wait, then pay <b>{lg.gbp(1650)}</b> for an emergency van: a whole vehicle for about 1,230 km, for one crate.</div>""",
        unsafe_allow_html=True,
    )
    st.markdown("### Closing: who pays, and the Stockholm test")
    if option_of(run, "recommended") and option_of(run, "baseline"):
        hold = current_hold_fee(run)
        imp = lg.impact(option_of(run, "recommended"), option_of(run, "baseline"), hold, p_miss)
        a, b, c = st.columns(3)
        a.markdown(f'<div class="sub">Cost if late</div><div class="bignum">{lg.gbp(imp["cost_if_late_ours"])} vs {lg.gbp(imp["cost_if_late_usual"])}</div>', unsafe_allow_html=True)
        b.markdown(f'<div class="sub">Spare time</div><div class="bignum">{imp["margin_ours_h"]:g} h</div>', unsafe_allow_html=True)
        c.markdown(f'<div class="sub">CO2e, modelled</div><div class="bignum">≈{imp["co2e_ours"]:.0f} vs ≈{imp["co2e_usual"]:.0f} kg</div>', unsafe_allow_html=True)
        st.markdown(f"Break-even at this fee: **{pct(imp['breakeven'])}**. Scenario: {lg.gbp(hold)} hold.")
    else:
        st.info("Run the agent first so the closing numbers come from the app. Never say a number that is not on screen.")
    st.markdown(
        """<div class="card"><b>Who pays:</b> suppliers pay per hold, carriers earn on space that would travel empty, every race weekend.<br>
<b>Stockholm test:</b> will suppliers set a standing spend policy and let the agent book holds without asking?
5 suppliers, one race weekend, SolvaPay buyer accounts with a £100 per-hold policy.
<b>Pass:</b> at least 4 of 5 keep their policy for the next race, carriers honour every hold, and no confirmed shipment misses its deadline.</div>""",
        unsafe_allow_html=True,
    )


{
    "Supplier ops": ops_view,
    "Buyer phone": phone_view,
    "Carrier": carrier_view,
    "Ledger": ledger_view,
    "Pitch": pitch_view,
}[view]()
