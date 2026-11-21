"""app.py: Safety Car demo UI (Person B). Run: streamlit run app.py

One screen for the demo: supplier ops on the left, "Sarah's phone" on the right.
Side effects (payments) happen only on button clicks. State lives in st.session_state
and in the payments object (data/state.json), which the phone view shares.

Backend: uses Person A's agent.py / payments.py when they are implemented. Until then it falls
back to the stand-ins in standins/ (and says so in the sidebar), so the UI can be built and tested early.
"""
from __future__ import annotations

import html as html_lib
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
GREEN = "#0E9F6E"
AMBER = "#C27803"
SLATE = "#64748B"
BLUE = "#1D4ED8"
STATUS_COLOURS = {"bookable now": GREEN, "fallback": SLATE, "conditional": AMBER, "blocked": RED}

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button {{font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;}}
.block-container {{padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1480px;}}
h1, h2, h3, h4 {{letter-spacing: -0.02em;}}
#MainMenu, footer {{visibility: hidden;}}
[data-testid="stHeader"] {{background: transparent;}}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] .brand {{display:flex;align-items:center;gap:10px;margin:4px 0 14px;}}
[data-testid="stSidebar"] .brand .logo {{width:34px;height:34px;border-radius:9px;background:{RED};display:grid;place-items:center;
  font-weight:800;color:#fff;font-size:0.95rem;box-shadow:0 4px 14px rgba(225,6,0,.45);}}
[data-testid="stSidebar"] .brand .name {{font-weight:800;font-size:1.15rem;color:#fff;line-height:1;}}
[data-testid="stSidebar"] .brand .tag {{font-size:0.72rem;color:#8B97AD;letter-spacing:.08em;text-transform:uppercase;}}
[data-testid="stSidebar"] .side-label {{font-size:0.7rem;letter-spacing:.12em;text-transform:uppercase;color:#8B97AD;margin:16px 0 6px;font-weight:600;}}
[data-testid="stSidebar"] .preview {{border-radius:10px;padding:10px 12px;font-size:0.88rem;line-height:1.35;margin:6px 0 4px;}}
[data-testid="stSidebar"] .preview.buy {{background:rgba(14,159,110,.14);border:1px solid rgba(14,159,110,.45);color:#B7F0D8;}}
[data-testid="stSidebar"] .preview.wait {{background:rgba(194,120,3,.14);border:1px solid rgba(194,120,3,.45);color:#FBE3B4;}}
[data-testid="stSidebar"] .foot {{font-size:0.75rem;color:#8B97AD;line-height:1.4;}}

/* ---------- hero ---------- */
.hero {{position:relative;overflow:hidden;border-radius:18px;padding:26px 28px 22px;margin-bottom:18px;color:#fff;
  background: radial-gradient(1200px 300px at 100% 0%, rgba(225,6,0,.38), transparent 60%),
              linear-gradient(135deg,#0B1220 0%,#141C2E 55%,#1D2638 100%);
  box-shadow:0 10px 30px rgba(11,18,32,.18);}}
.hero:after {{content:"";position:absolute;right:-40px;top:0;bottom:0;width:180px;opacity:.10;
  background: repeating-conic-gradient(#fff 0 25%, transparent 0 50%) 0 0/28px 28px;transform:skewX(-14deg);}}
.hero .eyebrow {{display:inline-flex;gap:8px;align-items:center;font-size:0.72rem;letter-spacing:.14em;text-transform:uppercase;
  color:#FFB4B0;font-weight:700;}}
.hero .eyebrow .dot {{width:8px;height:8px;border-radius:50%;background:{RED};box-shadow:0 0 0 4px rgba(225,6,0,.25);}}
.hero h1 {{font-size:2.3rem;font-weight:800;margin:6px 0 6px;color:#fff;padding:0;}}
.hero .lede {{font-size:1.05rem;color:#D3D9E4;max-width:760px;line-height:1.45;}}
.hero .lede b {{color:#fff;}}
.hero .chip {{display:inline-block;margin-top:12px;font-size:0.7rem;letter-spacing:.1em;text-transform:uppercase;
  border:1px solid rgba(255,255,255,.22);color:#C4CBD8;border-radius:999px;padding:3px 10px;}}

/* ---------- KPI tiles ---------- */
.kpis {{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:2px 0 16px;}}
.kpi {{background:#fff;border:1px solid #E3E6EB;border-radius:14px;padding:14px 16px;box-shadow:0 1px 2px rgba(16,24,40,.04);}}
.kpi .label {{font-size:0.72rem;letter-spacing:.08em;text-transform:uppercase;color:{SLATE};font-weight:600;}}
.kpi .value {{font-size:1.55rem;font-weight:800;color:#0B1220;margin-top:4px;line-height:1.15;white-space:nowrap;}}
.kpi .note {{font-size:0.8rem;color:{SLATE};margin-top:4px;}}
.kpi.red {{border-top:3px solid {RED};}} .kpi.green {{border-top:3px solid {GREEN};}}
.kpi.amber {{border-top:3px solid {AMBER};}} .kpi.slate {{border-top:3px solid #0B1220;}}
.kpi .vs {{font-size:0.8rem;color:{SLATE};margin-top:4px;}} .kpi .vs s {{color:#94A3B8;}}

/* ---------- section titles ---------- */
.section {{display:flex;align-items:baseline;gap:10px;margin:26px 0 10px;padding-bottom:8px;border-bottom:1px solid #E3E6EB;}}
.section .num {{font-size:0.72rem;font-weight:800;color:{RED};letter-spacing:.08em;}}
.section .title {{font-size:1.2rem;font-weight:800;color:#0B1220;}}
.section .sub {{font-size:0.85rem;color:{SLATE};margin-left:auto;}}

/* ---------- agent timeline ---------- */
.timeline {{position:relative;margin:6px 0 10px;padding-left:4px;}}
.step {{position:relative;display:flex;gap:14px;padding:10px 14px 10px 10px;margin-bottom:8px;background:#fff;border:1px solid #E3E6EB;
  border-left:4px solid #CBD5E1;border-radius:12px;}}
.step .ico {{flex:0 0 34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:1.05rem;background:#F1F5F9;}}
.step .t {{font-weight:700;color:#0B1220;font-size:0.95rem;line-height:1.3;}}
.step .d {{color:#475467;font-size:0.85rem;line-height:1.45;margin-top:2px;}}
.step.ok {{border-left-color:{GREEN};}} .step.ok .ico {{background:#E7F7F0;}}
.step.bad {{border-left-color:{RED};}} .step.bad .ico {{background:#FDECEC;}}
.step.warn {{border-left-color:{AMBER};}} .step.warn .ico {{background:#FDF3E1;}}
.step.shield {{border-left-color:#6D28D9;}} .step.shield .ico {{background:#F1EBFD;}}
.step.ask {{border-left-color:{BLUE};}} .step.ask .ico {{background:#E8EEFD;}}
.reasoning {{background:#0B1220;color:#E5E9F0;border-radius:14px;padding:16px 18px;margin:4px 0 14px;line-height:1.55;font-size:0.95rem;}}
.reasoning .k {{font-size:0.7rem;letter-spacing:.12em;text-transform:uppercase;color:#FF8A84;font-weight:700;margin-bottom:6px;}}

/* ---------- cards: receipt, approval, confirmation ---------- */
.card {{border:1px solid #E3E6EB;border-radius:14px;padding:14px 16px;margin-bottom:10px;background:#fff;color:#0B1220;
  box-shadow:0 1px 2px rgba(16,24,40,.04);}}
.card .k {{font-size:0.7rem;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:{SLATE};}}
.card .amount {{font-size:2.3rem;font-weight:800;line-height:1.1;margin:4px 0 8px;letter-spacing:-0.02em;}}
.card .row {{display:flex;gap:10px;font-size:0.86rem;line-height:1.4;padding:5px 0;border-top:1px dashed #E3E6EB;}}
.card .row .rk {{flex:0 0 92px;color:{SLATE};font-weight:600;}}
.card .row .rv {{flex:1;color:#1F2937;}}
.card .fine {{font-size:0.76rem;color:{SLATE};margin-top:8px;}}
.badge {{display:inline-block;font-size:0.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;border-radius:999px;padding:2px 8px;}}
.badge.green {{background:#E7F7F0;color:#05603A;}} .badge.red {{background:#FDECEC;color:#B42318;}}
.badge.blue {{background:#E8EEFD;color:#1E40AF;}} .badge.grey {{background:#F1F5F9;color:#475467;}}
.card.receipt {{border-top:4px solid {GREEN};}}
.card.approval {{border:2px solid {RED};background:linear-gradient(180deg,#FFF5F5 0%,#fff 55%);box-shadow:0 8px 24px rgba(225,6,0,.12);}}
.card.approval .amount {{color:{RED};font-size:2.8rem;}}
.card.confirm {{border-top:4px solid {BLUE};background:linear-gradient(180deg,#F3F6FF 0%,#fff 60%);}}
.card.confirm .amount {{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:1.7rem;color:{BLUE};}}
.card.empty {{text-align:center;color:{SLATE};padding:28px 16px;}}
.waiting {{display:flex;gap:10px;align-items:center;background:#FFF8EB;border:1px solid #F5D9A8;color:#7A4D00;border-radius:12px;
  padding:12px 14px;font-weight:600;margin:4px 0 12px;}}
.waiting .pulse {{width:10px;height:10px;border-radius:50%;background:{AMBER};animation:pulse 1.4s infinite;}}
@keyframes pulse {{0%{{box-shadow:0 0 0 0 rgba(194,120,3,.6)}}70%{{box-shadow:0 0 0 10px rgba(194,120,3,0)}}100%{{box-shadow:0 0 0 0 rgba(194,120,3,0)}}}}

/* ---------- phone ---------- */
.st-key-phone_ops, .st-key-phone_phone {{background:#F8FAFC;border:10px solid #0B1220;border-radius:36px;padding:18px 14px 16px !important;
  box-shadow:0 20px 50px rgba(11,18,32,.22);position:relative;}}
.phone-top {{display:flex;justify-content:space-between;align-items:center;font-size:0.75rem;font-weight:700;color:#0B1220;margin:-4px 4px 6px;}}
.phone-top .notch {{width:90px;height:20px;background:#0B1220;border-radius:0 0 14px 14px;margin-top:-22px;}}
.phone-head {{display:flex;gap:10px;align-items:center;margin:4px 2px 12px;}}
.phone-head .av {{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,{RED},#7A0A06);color:#fff;
  display:grid;place-items:center;font-weight:800;}}
.phone-head .n {{font-weight:700;font-size:0.95rem;color:#0B1220;line-height:1.2;}}
.phone-head .r {{font-size:0.76rem;color:{SLATE};}}
.hold-strip {{background:#0B1220;color:#E5E9F0;border-radius:12px;padding:10px 12px;font-size:0.86rem;margin:6px 0 8px;}}
.hold-strip b {{color:#fff;}}

/* ---------- impact ---------- */
.headline {{display:flex;align-items:center;gap:12px;background:linear-gradient(90deg,#E7F7F0,#F4FBF8);border:1px solid #B5E6D1;
  border-radius:14px;padding:14px 18px;margin:6px 0 14px;}}
.headline .big {{font-size:1.35rem;font-weight:800;color:#05603A;}}
.headline .small {{font-size:0.85rem;color:#2B6B52;}}
.callout {{background:#fff;border:1px solid #E3E6EB;border-left:4px solid #0B1220;border-radius:12px;padding:12px 16px;
  font-size:0.92rem;line-height:1.5;margin:10px 0;}}

/* ---------- streamlit widgets ---------- */
.stButton button {{border-radius:10px;font-weight:700;padding:0.55rem 1rem;transition:transform .05s ease, box-shadow .15s ease;}}
.stButton button[kind="primary"] {{box-shadow:0 6px 16px rgba(225,6,0,.28);}}
.stButton button:hover {{transform:translateY(-1px);}}
[data-testid="stExpander"] details {{border-radius:12px;background:#fff;}}
[data-testid="stDataFrame"] {{border-radius:12px;overflow:hidden;}}
[data-testid="stMetric"] {{background:#fff;border:1px solid #E3E6EB;border-radius:14px;padding:12px 16px;}}
.mono {{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:0.85rem;}}
</style>
""",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- html building blocks

esc = html_lib.escape


def kpi(label: str, value: str, note: str = "", tone: str = "") -> str:
    return (f'<div class="kpi {tone}"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>'
            + (f'<div class="note">{note}</div>' if note else "") + "</div>")


def kpis(*tiles: str) -> None:
    st.markdown('<div class="kpis">' + "".join(tiles) + "</div>", unsafe_allow_html=True)


def section(title: str, sub: str = "", num: str = "") -> None:
    st.markdown(
        f'<div class="section">' + (f'<span class="num">{esc(num)}</span>' if num else "")
        + f'<span class="title">{esc(title)}</span>' + (f'<span class="sub">{esc(sub)}</span>' if sub else "") + "</div>",
        unsafe_allow_html=True,
    )


def hero(title: str, lede: str, eyebrow: str = "Race-week freight agent", chip: str = "") -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow"><span class="dot"></span>{esc(eyebrow)}</div><h1>{esc(title)}</h1>'
        f'<div class="lede">{lede}</div>' + (f'<span class="chip">{esc(chip)}</span>' if chip else "") + "</div>",
        unsafe_allow_html=True,
    )


def step_tone(icon: str) -> str:
    if icon in ("✅",):
        return "ok"
    if icon in ("⛔", "🛑", "🚨"):
        return "bad"
    if icon in ("❓", "⚠️"):
        return "warn"
    if icon in ("🛡️", "🛡"):
        return "shield"
    if icon in ("📱",):
        return "ask"
    return ""


def kv_rows(pairs: List[tuple]) -> str:
    return "".join(f'<div class="row"><div class="rk">{esc(k)}</div><div class="rv">{esc(str(v))}</div></div>' for k, v in pairs if v)

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
    st.markdown(
        '<div class="brand"><div class="logo">SC</div><div><div class="name">Safety Car</div>'
        '<div class="tag">Race-week freight agent</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-label">View</div>', unsafe_allow_html=True)
    view = st.radio("View", ["Supplier ops", "Buyer phone", "Carrier", "Ledger", "Pitch"], label_visibility="collapsed")
    st.markdown('<div class="side-label">Scenario</div>', unsafe_allow_html=True)
    p_miss = st.slider("Chance the unit misses the truck", 0.0, 1.0, float(SHIP.p_miss_main_truck), 0.01, format="%.2f")
    try:
        import llm  # A's provider wrapper: reads LLM_PROVIDER and the key from .env
        HAS_LLM = llm.available()
    except Exception:  # no llm.py (stand-ins) or a broken SDK: stay on the replayed extraction
        HAS_LLM = False
    st.session_state.setdefault("use_llm", False)  # off by default: replayed is the safe stage default
    if not HAS_LLM:  # must be set before the widget is created
        st.session_state.use_llm = False
    st.toggle(
        "Live AI extraction",
        key="use_llm",
        disabled=not HAS_LLM,
        help="Reads the carrier messages with the AI model in .env. If a call fails, that message falls back to the replayed answers."
        if HAS_LLM
        else "No AI key in .env, so the demo uses the replayed (hand-checked) extraction.",
    )
    st.session_state.setdefault("fee_rise", False)

    # decision preview: makes no payment
    try:
        ev0 = None
        if hasattr(AGENT, "gather_offers"):
            # replayed offers only: the preview runs on every slider move, so no AI calls here
            got = AGENT.gather_offers(False, False)
            offers0 = list(got["offers"].values()) if isinstance(got, dict) else list(got[0])
            ev0 = lg.evaluate_all(offers0, SCN, FACTORS, p_miss)
    except Exception as exc:
        print(f"[app] decision preview: falling back to expected_offers.json ({type(exc).__name__}: {exc})", file=sys.stderr)
        ev0 = None
    if ev0 is None:
        raw = json.loads((DATA / "expected_offers.json").read_text(encoding="utf-8"))
        offers0 = [models.Offer(offer_id=f.split("_")[0], source_file=f, **v) for f, v in raw.items() if f != "nordlink_update.txt"]
        ev0 = lg.evaluate_all(offers0, SCN, FACTORS, p_miss)
    _by0 = {e.offer.offer_id: e for e in ev0}
    _nl, _base = _by0.get("nordlink"), _by0.get(SCN.baseline_offer_id)
    _hold_now = 120.0 if st.session_state.fee_rise else 60.0
    if _nl and _base:
        text, _be = lg.decision_preview(_hold_now, _nl.price_gbp, _base.price_gbp, p_miss)
        tone = "buy" if (_be is not None and p_miss > _be) else "wait"
        st.markdown(f'<div class="preview {tone}"><b>Decision preview</b><br>{esc(text)}</div>', unsafe_allow_html=True)

    st.markdown('<div class="side-label">Demo</div>', unsafe_allow_html=True)
    if st.button("↺ Reset demo", **STRETCH):
        PAY.reset()
        for k in ("run", "fee_rise", "confirmed"):
            st.session_state.pop(k, None)
        st.rerun()
    st.markdown(
        f'<div class="foot">Backend: {esc(BACKEND_LABEL)}<br>Fictional scenario. Prices are illustrative unless sourced.</div>',
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------- actions


def do_run(fee_rise: bool) -> None:
    st.session_state.fee_rise = fee_rise
    use_llm = bool(st.session_state.get("use_llm"))
    with st.spinner("Reading the carrier messages with the AI model…" if use_llm else "Running the agent…"):
        st.session_state.run = AGENT.run(SCN, FACTORS, PAY, p_miss=p_miss, fee_rise=fee_rise, use_llm=use_llm)


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
    phone = st.container(key=f"phone{key}")
    with phone:
        _phone_body(pending, holds, receipts, key)


def _phone_body(pending: Any, holds: List[Any], receipts: List[Any], key: str) -> None:
    initials = "".join(w[0] for w in SCN.buyer.approver.split()[:2]).upper()
    st.markdown(
        f'<div class="phone-top"><span>9:41</span><span class="notch"></span><span>●●● 5G</span></div>'
        f'<div class="phone-head"><div class="av">{esc(initials)}</div><div><div class="n">{esc(SCN.buyer.approver)}</div>'
        f'<div class="r">{esc(SCN.buyer.approver_role)} · {esc(SCN.buyer.company)}</div></div></div>',
        unsafe_allow_html=True,
    )

    if pending:
        kind = "Transport charge" if pending.kind == "transport" else "Holding fee"
        st.markdown(
            f'<div class="card approval"><span class="badge red">Approval needed · {esc(kind)}</span>'
            f'<div class="amount">{lg.gbp(pending.amount_gbp)}</div>'
            + kv_rows([
                ("Merchant", pending.merchant),
                ("For", pending.what_for),
                ("Why asked", ("; ".join(pending.policy_reasons) or "over policy")),
            ])
            + f'<div class="fine">{esc(pending.reason)}</div></div>',
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
            st.markdown('<div class="card empty">📭<br><b>No payments or approvals yet</b><br>Run the agent on the ops screen.</div>',
                        unsafe_allow_html=True)

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
        st.markdown(
            f'<div class="hold-strip">🛡️ <b>Hold in place</b> · {esc(active.merchant)} · {lg.gbp(active.amount_gbp)}'
            f'<br><span style="color:#9AA6BA">Bench test result decides what happens next.</span></div>',
            unsafe_allow_html=True,
        )
        paperwork = st.checkbox("Paperwork done (ATA Carnet / commercial invoice)", key=f"paper{key}")
        if st.button("Bench test failed → confirm the slot", key=f"conf{key}", type="primary", **STRETCH):
            res = do_confirm(paperwork)
            st.session_state.paperwork_warn = res.get("status") == "needs_paperwork"
            st.rerun()
        if st.button("Bench test passed → release the hold", key=f"rel{key}", **STRETCH):
            PAY.release(active.hold_id, NOW)
            st.rerun()
        if st.session_state.get("paperwork_warn") and not paperwork:
            st.warning("Paperwork first: tick the box once the ATA Carnet or commercial invoice is done.")
    if done and done.confirmation_ref:
        st.markdown(
            f'<div class="card confirm"><span class="badge blue">Carrier confirmation</span>'
            f'<div class="amount">{esc(done.confirmation_ref)}</div>'
            + kv_rows([
                ("Carrier", f"{done.merchant} · trunk NL-417"),
                ("Collection", "Daventry Tue 20:00"),
                ("ETA", "Monza Thu 09:00 CET"),
            ])
            + '<div class="fine">Simulated confirmation.</div></div>',
            unsafe_allow_html=True,
        )


def receipt_html(r: Any) -> str:
    return (
        f'<div class="card receipt"><div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span class="badge green">✓ Paid</span><span class="badge grey">Simulated · {esc(r.receipt_id)}</span></div>'
        f'<div class="amount">{lg.gbp(r.amount_gbp)}</div>'
        + kv_rows([
            ("Paid to", r.payee),
            ("For", r.paid_for),
            ("Not included", r.not_included),
            ("Authorised", r.authorisation),
        ])
        + f'<div class="fine">💳 {esc(r.card)}</div></div>'
    )


# --------------------------------------------------------------------------- ops view pieces


def status_pill(s: str) -> str:
    label = s.replace("_", " ")
    c = STATUS_COLOURS.get(label, SLATE)
    return (f'<span style="display:inline-flex;align-items:center;gap:6px;font-size:0.74rem;font-weight:700;'
            f'color:{c};background:{c}14;border:1px solid {c}55;border-radius:999px;padding:2px 9px;white-space:nowrap">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{c}"></span>{esc(label)}</span>')


MODE_ICONS = {"groupage_truck": "🚛", "dedicated_van": "🚐", "air_courier": "✈️", "local_hire": "🏪"}


def options_table(run: Any) -> None:
    rec = option_of(run, "recommended")
    rec_id = rec.offer.offer_id if rec is not None else None
    th = "padding:10px 12px;text-align:left;font-size:0.7rem;letter-spacing:.08em;text-transform:uppercase;color:#64748B;font-weight:700;white-space:nowrap"
    td = "padding:11px 12px;border-top:1px solid #EEF0F3;font-size:0.86rem;vertical-align:top"
    head = "".join(f'<th style="{th}">{h}</th>' for h in
                   ["Option", "Status", "Hold now", "Cost if used", "Expected", "Arrives", "Spare", "CO2e"])
    body = []
    for e in run.options:
        hold = e.offer.hold_fee_gbp
        is_rec = e.offer.offer_id == rec_id
        watch = e.issues + list(e.notes)[:2]
        watch_html = " · ".join(esc(w) for w in watch)
        star = (' <span style="font-size:0.66rem;font-weight:800;color:#fff;background:#E10600;border-radius:6px;'
                'padding:1px 6px;margin-left:4px;letter-spacing:.06em">PICK</span>') if is_rec else ""
        body.append(
            f'<tr style="{"background:#FFF7F6;" if is_rec else ""}">'
            f'<td style="{td};min-width:150px"><b>{MODE_ICONS.get(e.offer.mode or "", "📦")} {esc(e.offer.carrier or e.offer.offer_id)}</b>{star}'
            f'<br><span style="color:#64748B;font-size:0.78rem">{esc((e.offer.mode or "").replace("_", " "))}</span></td>'
            f'<td style="{td}">{status_pill(e.status)}</td>'
            f'<td style="{td};white-space:nowrap">{lg.gbp(hold) if hold else "—"}</td>'
            f'<td style="{td};white-space:nowrap">{lg.gbp(e.cost_if_used_gbp, 0)}</td>'
            f'<td style="{td};white-space:nowrap;font-weight:700">{lg.gbp(e.expected_cost_gbp, 0)}</td>'
            f'<td style="{td};white-space:nowrap">{esc(lg.fmt(e.arrival))}</td>'
            f'<td style="{td};white-space:nowrap">{esc(lg.hours_text(e.margin_h))}</td>'
            f'<td style="{td};white-space:nowrap">{esc(kg(e.co2e_kg))}</td></tr>'
            + (f'<tr style="{"background:#FFF7F6;" if is_rec else ""}"><td colspan="8" style="padding:0 12px 11px 12px;'
               f'font-size:0.79rem;color:#475467;line-height:1.45">⚠️ <b>Watch-outs:</b> {watch_html}</td></tr>' if watch else "")
        )
    st.markdown(
        '<div style="background:#fff;border:1px solid #E3E6EB;border-radius:14px;overflow-x:auto;box-shadow:0 1px 2px rgba(16,24,40,.04)">'
        f'<table style="width:100%;border-collapse:collapse"><thead><tr style="background:#F8FAFC">{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


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
    colour = alt.Scale(domain=list(STATUS_COLOURS), range=list(STATUS_COLOURS.values()))
    bars = alt.Chart(df).mark_bar(size=20, cornerRadius=6).encode(
        y=alt.Y("Option:N", sort=None, title=None),
        x=alt.X("start:T", title=None, axis=alt.Axis(format="%a %H:%M", labelAngle=0, tickCount=8)),
        x2="end:T",
        color=alt.Color("Status:N", scale=colour, legend=alt.Legend(orient="top", title=None, symbolType="circle")),
        tooltip=["Option", "Status", alt.Tooltip("start:T", format="%a %H:%M"), alt.Tooltip("end:T", format="%a %H:%M")],
    )
    rule = alt.Chart(pd.DataFrame({"d": [dl]})).mark_rule(color=RED, strokeDash=[6, 4], size=2.5).encode(x="d:T")
    label = alt.Chart(pd.DataFrame({"d": [dl], "t": [f"Deadline {lg.fmt(SHIP.deadline)}"]})).mark_text(
        align="right", dx=-6, dy=-8, color=RED, fontWeight="bold", fontSize=12
    ).encode(x="d:T", y=alt.value(0), text="t:N")
    chart = (bars + rule + label).properties(height=210, background="#FFFFFF", padding={"left": 8, "right": 16, "top": 24, "bottom": 6})
    chart = chart.configure_view(strokeWidth=0).configure_axis(
        labelFont="Inter", labelColor="#475467", labelFontSize=12, gridColor="#EEF0F3", domainColor="#E3E6EB", tickColor="#E3E6EB"
    ).configure_legend(labelFont="Inter", labelFontSize=12, labelColor="#475467")
    st.altair_chart(chart, **STRETCH)
    st.caption("Times in UTC. Each bar runs from departure to arrival if the unit fails its bench test.")


def impact_card(run: Any) -> None:
    rec, base = option_of(run, "recommended"), option_of(run, "baseline")
    section("Impact: usual plan vs Safety Car", "case: the unit fails its bench test", "05")
    if rec is None or base is None:
        st.info("Run the agent to see the comparison. (If the chance of a miss is below the break-even, it waits and buys nothing.)")
        return
    hold = current_hold_fee(run)
    imp = lg.impact(rec, base, hold, p_miss)
    scen = f"{lg.gbp(hold)} hold" + (", after the fee rise" if hold > POLICY.per_call_limit_gbp else "")
    approved = any(a.status == "approved" for a in state_lists()[3])
    if hold > POLICY.per_call_limit_gbp and approved:
        scen += ", approved by Sarah"
    st.caption(f"Scenario shown: **{scen}**, {p_miss:.0%} chance of a miss.")
    if imp["trips_avoided"]:
        st.markdown(
            '<div class="headline"><span style="font-size:1.6rem">🌍</span><div><div class="big">1 dedicated cross-border trip avoided</div>'
            f'<div class="small">The crate rides on a truck that is already going to Monza, instead of a van driving {imp["km_usual"]:,.0f} km for it alone.</div></div></div>',
            unsafe_allow_html=True,
        )
    kpis(
        kpi("Cost if late", lg.gbp(imp["cost_if_late_ours"]), f'vs <s>{lg.gbp(imp["cost_if_late_usual"])}</s> emergency van', "green"),
        kpi("Arrives", lg.fmt(imp["arrival_ours"]), f'{imp["margin_ours_h"]:g} h before the deadline', "slate"),
        kpi("CO2e (modelled)", f'≈{imp["co2e_ours"]:.0f} kg', f'vs <s>≈{imp["co2e_usual"]:.0f} kg</s> usual', "green"),
        kpi("Dedicated vehicle-km", f'{imp["km_ours"]:g}', f'vs <s>{imp["km_usual"]:,.0f}</s> usual', "green"),
    )

    rows = [
        ("Journey", f"{base.offer.carrier} dedicated van", f"{rec.offer.carrier}: pallet space on a truck already going"),
        ("Cost if the unit is late", lg.gbp(imp["cost_if_late_usual"]), lg.gbp(imp["cost_if_late_ours"])),
        ("Cost if it makes the truck", "£0", lg.gbp(hold)),
        ("Expected cost", lg.gbp(imp["expected_usual"]), lg.gbp(imp["expected_ours"])),
        ("Arrival", lg.fmt(imp["arrival_usual"]), lg.fmt(imp["arrival_ours"])),
        ("Spare time", lg.hours_text(imp["margin_usual_h"]), lg.hours_text(imp["margin_ours_h"])),
        ("Dedicated km", f'{imp["km_usual"]:,.0f}', f'{imp["km_ours"]:,.0f}'),
        ("CO2e (modelled)", kg(imp["co2e_usual"]), kg(imp["co2e_ours"])),
    ]
    th = "padding:12px 14px;text-align:left;font-size:0.72rem;letter-spacing:.08em;text-transform:uppercase;font-weight:700"
    td = "padding:10px 14px;border-top:1px solid #EEF0F3;font-size:0.88rem"
    body = "".join(
        f'<tr><td style="{td};color:#64748B;font-weight:600;width:28%">{esc(k)}</td>'
        f'<td style="{td};color:#475467">{esc(u)}</td>'
        f'<td style="{td};background:#F3FBF7;font-weight:700;color:#05603A">{esc(o)}</td></tr>'
        for k, u, o in rows
    )
    st.markdown(
        '<div style="background:#fff;border:1px solid #E3E6EB;border-radius:14px;overflow:hidden;margin-top:4px">'
        '<table style="width:100%;border-collapse:collapse"><thead><tr>'
        f'<th style="{th};color:#64748B;background:#F8FAFC"></th>'
        f'<th style="{th};color:#64748B;background:#F8FAFC">Usual plan: wait, then emergency van</th>'
        f'<th style="{th};color:#fff;background:#0E9F6E">Safety Car: hold now</th>'
        f'</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )
    be = imp["breakeven"]
    st.markdown(
        f'<div class="callout"><b>Expected cost at {p_miss:.0%}:</b> {lg.gbp(imp["expected_ours"])} with the hold vs '
        f'{lg.gbp(imp["expected_usual"])} waiting. The hold pays for itself above a <b>{pct(be)}</b> chance of a miss.<br>'
        f'The van would arrive <b>{imp["later_by_h"]:.0f} h earlier</b>. We still arrive <b>{imp["margin_ours_h"]:g} h before</b> '
        "the deadline: paying for speed nobody needs is the waste we remove.</div>",
        unsafe_allow_html=True,
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
    section("What the AI read", "every value is checked against the original words", "06")
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
    section("Assumptions and sources", "every number on screen has a source or an illustrative label", "07")
    rows = []
    for group in ("emission_factors", "distances_km", "assumptions"):
        for key, v in FACTORS.get(group, {}).items():
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
    hero(
        "Safety Car",
        "<b>£60 on Monday beats £1,650 on Wednesday.</b> An agent that buys the backup before you know you need it, "
        "inside rules the boss set once.",
        eyebrow=f"Shipment at risk · {SHIP.item}" if getattr(SHIP, "item", None) else "Shipment at risk",
        chip=SCN.label,
    )
    risk_tone = "red" if p_miss >= 0.2 else "amber"
    kpis(
        kpi("Deadline at Monza", lg.fmt(SHIP.deadline), "garage needs the unit", "slate"),
        kpi("Main truck leaves", lg.fmt(SHIP.main_truck_departure), "the usual truck to Monza", "slate"),
        kpi("Bench-test result", lg.fmt(SHIP.bench_test_result_at), "when we know it's late", "amber"),
        kpi("Chance of a miss", f"{p_miss:.0%}", "move the slider to test", risk_tone),
    )

    left, right = st.columns([1.7, 1], gap="large")
    with right:
        phone_panel(run, key="_ops")
    with left:
        r1, r2 = st.columns([1.15, 1])
        r1.button("▶  Run the Safety Car agent", type="primary", **STRETCH,
                  on_click=lambda: (PAY.reset(), do_run(False)))
        r2.button("↻  Replay: fee rises to £120", **STRETCH,
                  on_click=lambda: (PAY.reset(), do_run(True)))

        if run is None:
            st.markdown(
                '<div class="card empty" style="margin-top:14px">🏁<br><b>Ready when you are</b><br>'
                "Run the agent: it reads the carrier messages, checks every option against the deadline and the small print, "
                "and decides what to buy within the spend policy.</div>",
                unsafe_allow_html=True,
            )
            return

        section("Agent log", "what the agent did, in order", "01")
        steps_html = []
        for s in run.steps:
            icon, title, detail = step_parts(s)
            steps_html.append(
                f'<div class="step {step_tone(icon)}"><div class="ico">{esc(icon)}</div><div>'
                f'<div class="t">{esc(title)}</div>' + (f'<div class="d">{esc(detail)}</div>' if detail else "") + "</div></div>"
            )
        st.markdown('<div class="timeline">' + "".join(steps_html) + "</div>", unsafe_allow_html=True)
        if getattr(run, "explanation", ""):
            st.markdown(f'<div class="reasoning"><div class="k">Agent’s reasoning</div>{esc(run.explanation)}</div>',
                        unsafe_allow_html=True)

        section("Payment", "simulated SolvaPay buyer account", "02")
        _, _, receipts, approvals = state_lists()
        pend = next((a for a in approvals if a.status == "pending"), None)
        if pend:
            st.markdown(
                f'<div class="waiting"><span class="pulse"></span>Waiting for {esc(POLICY.owner)}’s approval of '
                f'{lg.gbp(pend.amount_gbp)}: approve it on the phone →</div>',
                unsafe_allow_html=True,
            )
        elif receipts:
            st.markdown(receipt_html(receipts[-1]), unsafe_allow_html=True)
        else:
            st.markdown('<div class="card empty">No payment: the agent decided to wait.</div>', unsafe_allow_html=True)

    if run is None:
        return
    # full width below the log and the phone: the wide tables and the chart need the room
    section("Options", "ranked by status, then expected cost", "03")
    options_table(run)
    section("Pit window", "departure to arrival vs the deadline", "04")
    pit_window_chart(run)
    impact_card(run)
    what_the_ai_read(run)
    assumptions_table()


def phone_view() -> None:
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid:
        phone_panel(st.session_state.get("run"), key="_phone")
        if st.button("↻ Refresh", **STRETCH):
            st.rerun()


def carrier_view() -> None:
    hero(
        "Nordlink Groupage",
        "The same money, seen from the carrier: <b>revenue on space that would otherwise travel empty.</b> "
        "Built live from the payments state.",
        eyebrow="Carrier view · trunk NL-417",
    )
    _, holds, receipts, _ = state_lists()
    mine = [h for h in holds if h.offer_id == "nordlink"]
    hold_receipts = {h.receipt_id for h in mine if h.receipt_id}
    mine_ids = {h.hold_id for h in mine}
    fees = sum(r.amount_gbp for r in receipts if r.receipt_id in hold_receipts)
    transport = sum(r.amount_gbp for r in receipts if r.hold_id in mine_ids and r.receipt_id not in hold_receipts)
    kpis(
        kpi("Trunk", "NL-417", "Daventry hub → Monza paddock", "slate"),
        kpi("Spare spaces sold as holds", str(len(mine)), "1 spare pallet space", "amber"),
        kpi("Holding fees earned", lg.gbp(fees), "kept even if the slot is released", "green"),
        kpi("Transport confirmed", lg.gbp(transport), "billed only if the slot is used", "green"),
    )
    st.markdown(
        '<div class="callout">Trunk NL-417, Daventry hub to Monza paddock, departs Tue 21:00 UK, ETA Thu 09:00 CET. '
        "One spare pallet space, held for the buyer until Tue 18:00.</div>",
        unsafe_allow_html=True,
    )
    section("Holds sold", "from the buyer's SolvaPay account")
    if not mine:
        st.markdown('<div class="card empty">No holds sold yet.<br>Run the agent on the Supplier ops view.</div>', unsafe_allow_html=True)
    for h in mine:
        tone = {"held": "blue", "used": "green", "released": "grey"}.get(h.status, "grey")
        extra = []
        if h.confirmation_ref:
            extra.append(("Confirmation", h.confirmation_ref))
        if h.status == "released":
            extra.append(("Note", "Fee kept even though the slot was released"))
        st.markdown(
            f'<div class="card"><div style="display:flex;justify-content:space-between;align-items:center">'
            f'<b class="mono">{esc(h.hold_id)}</b><span class="badge {tone}">{esc(h.status)}</span></div>'
            f'<div class="amount" style="font-size:1.6rem">{lg.gbp(h.amount_gbp)}</div>'
            + kv_rows([("For", h.what_for)] + extra) + "</div>",
            unsafe_allow_html=True,
        )


def ledger_view() -> None:
    hero("Ledger", "Every policy check, approval request, decision, charge and release, <b>recorded as it happens.</b>",
         eyebrow="Buyer account · audit trail")
    ledger, holds, receipts, approvals = state_lists()
    kpis(
        kpi("Ledger entries", str(len(ledger)), "", "slate"),
        kpi("Holds", str(len(holds)), "", "amber"),
        kpi("Approvals", str(len(approvals)), f'{sum(1 for a in approvals if a.status == "pending")} pending', "red"),
        kpi("Total charged", lg.gbp(sum(r.amount_gbp for r in receipts)), "simulated", "green"),
    )
    section("Ledger", "newest last")
    if not ledger:
        st.markdown('<div class="card empty">Nothing on the ledger yet.</div>', unsafe_allow_html=True)
    else:
        st.dataframe(
            pd.DataFrame([{"At": x.at, "Kind": x.kind, "Detail": x.detail, "£": x.amount_gbp} for x in ledger]),
            hide_index=True, **STRETCH,
        )
    section("Holds")
    st.dataframe(pd.DataFrame([h.model_dump(mode="json") for h in holds]) if holds else pd.DataFrame(), hide_index=True, **STRETCH)
    section("Approvals")
    st.dataframe(pd.DataFrame([a.model_dump(mode="json") for a in approvals]) if approvals else pd.DataFrame(), hide_index=True, **STRETCH)


def pitch_view() -> None:
    run = st.session_state.get("run")
    van_km = lg.dist(FACTORS, "mk_to_monza")
    hero(
        SCN.buyer.company,
        f"Milton Keynes supplier. The truck to Monza leaves <b>{esc(lg.fmt(SHIP.main_truck_departure))}</b>. "
        f"One timing unit is still on the bench: <b>{SHIP.p_miss_main_truck:.0%}</b> chance it misses the truck. "
        f"The garage needs it by <b>{esc(lg.fmt(SHIP.deadline))}</b>.<br>"
        f"Today: wait, then pay <b>{lg.gbp(1650)}</b> for an emergency van: a whole vehicle for about {van_km:,.0f} km, for one crate.",
        eyebrow="Opening · the buyer and the shipment at risk",
    )
    section("Closing: who pays, and the Stockholm test")
    if option_of(run, "recommended") and option_of(run, "baseline"):
        hold = current_hold_fee(run)
        imp = lg.impact(option_of(run, "recommended"), option_of(run, "baseline"), hold, p_miss)
        kpis(
            kpi("Cost if late", lg.gbp(imp["cost_if_late_ours"]), f'vs <s>{lg.gbp(imp["cost_if_late_usual"])}</s>', "green"),
            kpi("Spare time", f'{imp["margin_ours_h"]:g} h', "before the deadline", "slate"),
            kpi("CO2e, modelled", f'≈{imp["co2e_ours"]:.0f} kg', f'vs <s>≈{imp["co2e_usual"]:.0f} kg</s>', "green"),
            kpi("Break-even", pct(imp["breakeven"]), f"at a {lg.gbp(hold)} hold", "amber"),
        )
    else:
        st.markdown('<div class="card empty">Run the agent first so the closing numbers come from the app.<br>'
                    "Never say a number that is not on screen.</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.markdown(
        '<div class="card" style="height:100%"><span class="badge green">Who pays</span><div style="margin-top:8px;line-height:1.55">'
        "Suppliers pay per hold. Carriers earn on space that would travel empty. Every race weekend.</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        '<div class="card" style="height:100%"><span class="badge blue">Stockholm test</span><div style="margin-top:8px;line-height:1.55">'
        "Will suppliers set a standing spend policy and let the agent book holds without asking? "
        "5 suppliers, one race weekend, SolvaPay buyer accounts with a £100 per-hold policy.<br>"
        "<b>Pass:</b> at least 4 of 5 keep their policy for the next race, carriers honour every hold, "
        "and no confirmed shipment misses its deadline.</div></div>",
        unsafe_allow_html=True,
    )


{
    "Supplier ops": ops_view,
    "Buyer phone": phone_view,
    "Carrier": carrier_view,
    "Ledger": ledger_view,
    "Pitch": pitch_view,
}[view]()
