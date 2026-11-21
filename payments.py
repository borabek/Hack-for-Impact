"""SolvaPay-style buyer payments, simulated (CLAUDE.md section 7). Owner: Person A.

Mirrors SolvaPay's buyer account: each agent has an ID and a spend policy (limits per call, day and
month, allowed merchants, a stated purpose). Over a limit, the agent asks its owner with the amount
and the reason; the owner approves or declines; every step lands on a ledger. The agent never sees
the card and cannot approve its own request.

State lives in a JSON file so the ops screen and the phone screen (separate Streamlit sessions)
share it. Every public method reloads the file first and saves after changing it.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from models import ApprovalRequest, Buyer, Hold, LedgerEntry, PolicyDecision, Receipt, SpendPolicy

CARD = "Visa ending 4242, stored in the buyer account (the agent never sees card details)"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _money(x: float) -> str:
    return f"£{x:,.0f}" if float(x).is_integer() else f"£{x:,.2f}"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6].upper()}"


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


class Payments:
    def __init__(self, policy: SpendPolicy, buyer: Buyer, path: str | Path = "data/state.json"):
        self.policy = policy
        self.buyer = buyer
        self.path = Path(path)
        self._state: dict = {}
        self._load()

    # ------------------------------------------------------------------ state
    def _empty(self) -> dict:
        return {"holds": [], "approvals": [], "receipts": [], "ledger": []}

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._state = {
                "holds": [Hold.model_validate(h) for h in raw.get("holds", [])],
                "approvals": [ApprovalRequest.model_validate(a) for a in raw.get("approvals", [])],
                "receipts": [Receipt.model_validate(r) for r in raw.get("receipts", [])],
                "ledger": [LedgerEntry.model_validate(e) for e in raw.get("ledger", [])],
            }
        except FileNotFoundError:
            self._state = self._empty()
        except Exception as exc:  # corrupt file: never crash the demo
            print(f"payments: could not read {self.path} ({exc}); starting empty", file=sys.stderr)
            self._state = self._empty()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: [m.model_dump(mode="json") for m in v] for k, v in self._state.items()}
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".state-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def _log(self, at: datetime, kind: str, detail: str, amount: Optional[float] = None) -> None:
        self._state["ledger"].append(LedgerEntry(at=at, kind=kind, detail=detail, amount_gbp=amount))

    # Read-only views for the UI (always fresh from disk).
    @property
    def holds(self) -> list[Hold]:
        self._load()
        return list(self._state["holds"])

    @property
    def approvals(self) -> list[ApprovalRequest]:
        self._load()
        return list(self._state["approvals"])

    @property
    def receipts(self) -> list[Receipt]:
        self._load()
        return list(self._state["receipts"])

    @property
    def ledger(self) -> list[LedgerEntry]:
        self._load()
        return list(self._state["ledger"])

    # ---------------------------------------------------------------- helpers
    def _find_hold(self, hold_id: str) -> Hold:
        for h in self._state["holds"]:
            if h.hold_id == hold_id:
                return h
        raise KeyError(f"unknown hold {hold_id}")

    def _find_approval(self, approval_id: str) -> ApprovalRequest:
        for a in self._state["approvals"]:
            if a.approval_id == approval_id:
                return a
        raise KeyError(f"unknown approval {approval_id}")

    def _active_hold(self, offer_id: str) -> Optional[Hold]:
        for h in reversed(self._state["holds"]):
            if h.offer_id == offer_id and h.status == "held":
                return h
        return None

    def _pending(self, offer_id: Optional[str] = None, kind: Optional[str] = None,
                 hold_id: Optional[str] = None) -> Optional[ApprovalRequest]:
        for a in reversed(self._state["approvals"]):
            if a.status != "pending":
                continue
            if offer_id is not None and a.offer_id != offer_id:
                continue
            if kind is not None and a.kind != kind:
                continue
            if hold_id is not None and a.hold_id != hold_id:
                continue
            return a
        return None

    def _spent(self, at: datetime, period: Literal["day", "month"]) -> float:
        ref = at.astimezone(timezone.utc)
        total = 0.0
        for r in self._state["receipts"]:
            t = r.issued_at.astimezone(timezone.utc)
            same = t.date() == ref.date() if period == "day" else (t.year, t.month) == (ref.year, ref.month)
            if same:
                total += r.amount_gbp
        return total

    def _policy_text(self) -> str:
        return (f"{self.policy.owner}'s policy: up to {_money(self.policy.per_call_limit_gbp)} per hold, "
                f"approved carrier, purpose '{self.policy.purpose}'")

    def _check(self, merchant: str, amount: float, purpose: str, at: datetime) -> PolicyDecision:
        p = self.policy
        allowed = {_norm(m) for m in p.allowed_merchants}
        if _norm(merchant) not in allowed:
            return PolicyDecision(status="denied", reasons=[f"{merchant} is not an approved merchant"])
        if _norm(purpose) != _norm(p.purpose):
            return PolicyDecision(status="denied", reasons=[
                f"Purpose '{purpose}' differs from the stated purpose '{p.purpose}'"])
        if amount is None or amount <= 0:
            return PolicyDecision(status="denied", reasons=["Amount must be positive"])
        reasons = []
        if amount > p.per_call_limit_gbp:
            reasons.append(f"{_money(amount)} is above the {_money(p.per_call_limit_gbp)} per-hold limit")
        day = self._spent(at, "day")
        if day + amount > p.daily_limit_gbp:
            reasons.append(f"it would take today's spend to {_money(day + amount)}, over the "
                           f"{_money(p.daily_limit_gbp)} daily limit")
        month = self._spent(at, "month")
        if month + amount > p.monthly_limit_gbp:
            reasons.append(f"it would take this month's spend to {_money(month + amount)}, over the "
                           f"{_money(p.monthly_limit_gbp)} monthly limit")
        if reasons:
            return PolicyDecision(status="needs_approval", reasons=reasons)
        return PolicyDecision(status="allowed", reasons=[f"Within {self._policy_text()}"])

    def _charge(self, *, kind: str, hold: Hold, merchant: str, amount: float, paid_for: str,
                not_included: str, cancellation: str, authorisation: str, at: datetime,
                approval_id: Optional[str] = None) -> Receipt:
        receipt = Receipt(
            receipt_id=_new_id("R"), kind=kind, hold_id=hold.hold_id, approval_id=approval_id,
            payer=self.buyer.company, agent_id=self.policy.agent_id, card=CARD, payee=merchant,
            amount_gbp=amount, paid_for=paid_for, not_included=not_included,
            authorisation=authorisation, cancellation=cancellation, issued_at=at,
        )
        self._state["receipts"].append(receipt)
        self._log(at, "charge", f"{_money(amount)} to {merchant}: {paid_for} (receipt {receipt.receipt_id}, simulated)",
                  amount)
        return receipt

    def _new_hold(self, *, offer_id: str, merchant: str, amount: float, what_for: str, at: datetime) -> Hold:
        hold = Hold(hold_id=_new_id("H"), offer_id=offer_id, merchant=merchant, amount_gbp=amount,
                    what_for=what_for, created_at=at)
        self._state["holds"].append(hold)
        return hold

    def _mark_used(self, hold: Hold, what_for: str, at: datetime) -> None:
        m = re.search(r"\b([A-Z]{2,}-\d+)\b", what_for or "")
        prefix = m.group(1) if m else "SC"
        hold.status = "used"
        hold.confirmation_ref = f"{prefix}-{uuid.uuid4().hex[:4].upper()}"
        self._log(at, "confirmed", f"Carrier confirmed the slot for hold {hold.hold_id}: ref {hold.confirmation_ref}")

    def _approval_authorisation(self, a: ApprovalRequest) -> str:
        if a.amount_gbp > self.policy.per_call_limit_gbp:
            why = f"it was over the {_money(self.policy.per_call_limit_gbp)} limit"
        else:
            why = "it was over the daily or monthly limit"
        return f"Approved by {self.policy.owner} ({self.buyer.approver_role}) because {why}"

    # ------------------------------------------------------------- public API
    def check_policy(self, merchant: str, amount: float, purpose: str, at: Optional[datetime] = None) -> PolicyDecision:
        at = at or _now()
        self._load()
        decision = self._check(merchant, amount, purpose, at)
        self._log(at, "policy_check", f"{_money(amount)} to {merchant}: {decision.status} ({'; '.join(decision.reasons)})",
                  amount)
        self._save()
        return decision

    def reserve(self, *, offer_id: str, merchant: str, amount: float, what_for: str, not_included: str,
                cancellation: str, purpose: str, reason: str, at: Optional[datetime] = None) -> dict:
        at = at or _now()
        self._load()
        held = self._active_hold(offer_id)
        if held:
            self._log(at, "already_held", f"Hold {held.hold_id} with {held.merchant} is already active; no new charge")
            self._save()
            return {"status": "already_held", "hold": held, "receipt": self._receipt_for(held.hold_id)}
        pending = self._pending(offer_id=offer_id, kind="hold")
        if pending:
            self._log(at, "already_pending", f"Approval {pending.approval_id} is already waiting for {pending.owner}")
            self._save()
            return {"status": "approval_requested", "approval": pending, "existing": True}

        decision = self._check(merchant, amount, purpose, at)
        self._log(at, "policy_check", f"{_money(amount)} to {merchant}: {decision.status} ({'; '.join(decision.reasons)})",
                  amount)
        if decision.status == "denied":
            self._log(at, "denied", f"Blocked by policy: {'; '.join(decision.reasons)}", amount)
            self._save()
            return {"status": "denied", "decision": decision}
        if decision.status == "needs_approval":
            approval = ApprovalRequest(
                approval_id=_new_id("A"), kind="hold", agent_id=self.policy.agent_id, owner=self.policy.owner,
                offer_id=offer_id, merchant=merchant, amount_gbp=amount, purpose=purpose, reason=reason,
                policy_reasons=decision.reasons, what_for=what_for, not_included=not_included,
                cancellation=cancellation, created_at=at,
            )
            self._state["approvals"].append(approval)
            self._log(at, "approval_requested",
                      f"Asked {self.policy.owner} to approve {_money(amount)} to {merchant}: {'; '.join(decision.reasons)}",
                      amount)
            self._save()
            return {"status": "approval_requested", "approval": approval, "decision": decision}

        hold = self._new_hold(offer_id=offer_id, merchant=merchant, amount=amount, what_for=what_for, at=at)
        receipt = self._charge(kind="hold", hold=hold, merchant=merchant, amount=amount, paid_for=what_for,
                               not_included=not_included, cancellation=cancellation,
                               authorisation=f"Within {self._policy_text()}. Paid automatically by agent "
                                             f"{self.policy.agent_id}.", at=at)
        hold.receipt_id = receipt.receipt_id
        self._save()
        return {"status": "booked", "hold": hold, "receipt": receipt, "decision": decision}

    def decide(self, approval_id: str, approve: bool, by: str, at: Optional[datetime] = None) -> Optional[Receipt]:
        at = at or _now()
        self._load()
        if by != self.policy.owner:
            who = "the agent itself" if by == self.policy.agent_id else by
            self._log(at, "blocked", f"Refused a decision on {approval_id} by {who}: only {self.policy.owner} can decide")
            self._save()
            raise PermissionError(f"Only {self.policy.owner} can approve or decline; {who} cannot")
        a = self._find_approval(approval_id)
        if a.status != "pending":
            self._log(at, "ignored", f"Approval {approval_id} was already {a.status}; nothing changed")
            self._save()
            return None
        a.decided_at, a.decided_by = at, by
        if not approve:
            a.status = "declined"
            self._log(at, "declined", f"{by} declined {_money(a.amount_gbp)} to {a.merchant}; no charge", a.amount_gbp)
            self._save()
            return None

        a.status = "approved"
        self._log(at, "approved", f"{by} approved {_money(a.amount_gbp)} to {a.merchant}", a.amount_gbp)
        auth = self._approval_authorisation(a)
        if a.kind == "hold":
            hold = self._new_hold(offer_id=a.offer_id, merchant=a.merchant, amount=a.amount_gbp,
                                  what_for=a.what_for, at=at)
            receipt = self._charge(kind="hold", hold=hold, merchant=a.merchant, amount=a.amount_gbp,
                                   paid_for=a.what_for, not_included=a.not_included, cancellation=a.cancellation,
                                   authorisation=auth, at=at, approval_id=a.approval_id)
            hold.receipt_id = receipt.receipt_id
        else:
            hold = self._find_hold(a.hold_id)
            receipt = self._charge(kind="transport", hold=hold, merchant=a.merchant, amount=a.amount_gbp,
                                   paid_for=a.what_for, not_included=a.not_included, cancellation=a.cancellation,
                                   authorisation=auth, at=at, approval_id=a.approval_id)
            self._mark_used(hold, a.what_for, at)
        self._save()
        return receipt

    def confirm(self, hold_id: str, *, amount: float, what_for: str, paperwork_done: bool, purpose: str,
                reason: str, at: Optional[datetime] = None, not_included: str = "",
                cancellation: str = "") -> dict:
        at = at or _now()
        self._load()
        hold = self._find_hold(hold_id)
        if hold.status == "used":
            return {"status": "already_confirmed", "hold": hold, "confirmation_ref": hold.confirmation_ref,
                    "receipt": self._transport_receipt(hold.hold_id)}
        if hold.status != "held":
            self._log(at, "confirm_blocked", f"Hold {hold_id} is {hold.status}; it can't be confirmed")
            self._save()
            return {"status": "not_active", "hold": hold}
        pending = self._pending(kind="transport", hold_id=hold_id)
        if pending:
            return {"status": "approval_requested", "approval": pending, "existing": True}
        if not paperwork_done:
            self._log(at, "needs_paperwork",
                      f"Confirming hold {hold_id} blocked: paperwork (ATA Carnet or commercial invoice) not done")
            self._save()
            return {"status": "needs_paperwork", "hold": hold}

        not_included = not_included or (f"The {_money(hold.amount_gbp)} holding fee, already paid"
                                        + (f" (receipt {hold.receipt_id})" if hold.receipt_id else ""))
        decision = self._check(hold.merchant, amount, purpose, at)
        self._log(at, "policy_check",
                  f"{_money(amount)} to {hold.merchant}: {decision.status} ({'; '.join(decision.reasons)})", amount)
        if decision.status == "denied":
            self._log(at, "denied", f"Blocked by policy: {'; '.join(decision.reasons)}", amount)
            self._save()
            return {"status": "denied", "decision": decision}
        if decision.status == "needs_approval":
            approval = ApprovalRequest(
                approval_id=_new_id("A"), kind="transport", hold_id=hold_id, agent_id=self.policy.agent_id,
                owner=self.policy.owner, offer_id=hold.offer_id, merchant=hold.merchant, amount_gbp=amount,
                purpose=purpose, reason=reason, policy_reasons=decision.reasons, what_for=what_for,
                not_included=not_included, cancellation=cancellation, created_at=at,
            )
            self._state["approvals"].append(approval)
            self._log(at, "approval_requested",
                      f"Asked {self.policy.owner} to approve {_money(amount)} transport to {hold.merchant}: "
                      f"{'; '.join(decision.reasons)}", amount)
            self._save()
            return {"status": "approval_requested", "approval": approval, "decision": decision}

        receipt = self._charge(kind="transport", hold=hold, merchant=hold.merchant, amount=amount, paid_for=what_for,
                               not_included=not_included, cancellation=cancellation,
                               authorisation=f"Within {self._policy_text()}. Paid automatically by agent "
                                             f"{self.policy.agent_id}.", at=at)
        self._mark_used(hold, what_for, at)
        self._save()
        return {"status": "confirmed", "hold": hold, "receipt": receipt, "confirmation_ref": hold.confirmation_ref}

    def release(self, hold_id: str, at: Optional[datetime] = None) -> Hold:
        at = at or _now()
        self._load()
        hold = self._find_hold(hold_id)
        if hold.status == "held":
            hold.status = "released"
            self._log(at, "release", f"Released hold {hold_id} with {hold.merchant}; the "
                                     f"{_money(hold.amount_gbp)} fee is non-refundable")
            self._save()
        return hold

    def active_hold(self, offer_id: str) -> Optional[Hold]:
        self._load()
        return self._active_hold(offer_id)

    def pending_approval(self, offer_id: Optional[str] = None) -> Optional[ApprovalRequest]:
        self._load()
        return self._pending(offer_id=offer_id)

    def _receipt_for(self, hold_id: str) -> Optional[Receipt]:
        for r in self._state["receipts"]:
            if r.hold_id == hold_id and r.kind == "hold":
                return r
        return None

    def _transport_receipt(self, hold_id: str) -> Optional[Receipt]:
        for r in self._state["receipts"]:
            if r.hold_id == hold_id and r.kind == "transport":
                return r
        return None

    def receipt_for(self, hold_id: str) -> Optional[Receipt]:
        """The holding-fee receipt for a hold."""
        self._load()
        return self._receipt_for(hold_id)

    def transport_receipt(self, hold_id: str) -> Optional[Receipt]:
        self._load()
        return self._transport_receipt(hold_id)

    def last_receipt(self) -> Optional[Receipt]:
        self._load()
        return self._state["receipts"][-1] if self._state["receipts"] else None

    def latest_hold(self) -> Optional[Hold]:
        self._load()
        return self._state["holds"][-1] if self._state["holds"] else None

    def spent(self, at: Optional[datetime] = None, period: Literal["day", "month"] = "day") -> float:
        self._load()
        return self._spent(at or _now(), period)

    def reset(self) -> None:
        self._state = self._empty()
        self._save()
