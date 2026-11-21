"""Pydantic models shared by every module (CLAUDE.md section 6). Owner: Person A.

All datetimes are timezone-aware. Everything on Offer is optional except offer_id and
source_file, because the LLM must return null for anything a carrier didn't state.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Mode = Literal["groupage_truck", "dedicated_van", "air_courier", "local_hire"]
OptionStatus = Literal["bookable_now", "fallback", "conditional", "blocked"]

# Fields of Offer that hold a single value (used by verify / merge / compare).
SCALAR_FIELDS = [
    "carrier", "mode", "service", "hold_fee_gbp", "price_gbp", "price_eur",
    "collection_cutoff", "departure", "arrival", "collection_hours", "transit_hours",
    "confirm_by", "latest_booking", "crew", "max_weight_kg_per_piece",
    "cancellation_terms", "emissions_claim",
]
NUMERIC_FIELDS = {
    "hold_fee_gbp", "price_gbp", "price_eur", "collection_hours", "transit_hours",
    "crew", "max_weight_kg_per_piece",
}
DATETIME_FIELDS = {"collection_cutoff", "departure", "arrival", "confirm_by", "latest_booking"}
LIST_FIELDS = ["assumptions", "limitations", "flags"]


class Offer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    offer_id: str
    source_file: str
    carrier: Optional[str] = None
    mode: Optional[Mode] = None
    service: Optional[str] = None
    hold_fee_gbp: Optional[float] = None
    price_gbp: Optional[float] = None
    price_eur: Optional[float] = None
    collection_cutoff: Optional[AwareDatetime] = None
    departure: Optional[AwareDatetime] = None
    arrival: Optional[AwareDatetime] = None
    collection_hours: Optional[float] = None
    transit_hours: Optional[float] = None
    confirm_by: Optional[AwareDatetime] = None
    latest_booking: Optional[AwareDatetime] = None
    crew: Optional[int] = None
    max_weight_kg_per_piece: Optional[float] = None
    cancellation_terms: Optional[str] = None
    emissions_claim: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)


class QuoteCheck(BaseModel):
    field: str
    quote: str
    verified: bool
    score: float
    note: str = ""


# ---- scenario (exactly the shape of data/scenario.json) ----

class Shipment(BaseModel):
    shipment_id: str
    item: str
    weight_kg: float
    dims_cm: str
    contains_lithium_battery: bool
    origin: str
    destination: str
    deadline: AwareDatetime
    main_truck_departure: AwareDatetime
    bench_test_result_at: AwareDatetime
    ready_if_test_fails: AwareDatetime
    p_miss_main_truck: float
    carnet_listed: bool


class SpendPolicy(BaseModel):
    agent_id: str
    owner: str
    per_call_limit_gbp: float
    daily_limit_gbp: float
    monthly_limit_gbp: float
    allowed_merchants: list[str]
    purpose: str


class Buyer(BaseModel):
    company: str
    approver: str
    approver_role: str


class Scenario(BaseModel):
    label: str
    now: AwareDatetime
    buyer: Buyer
    shipment: Shipment
    policy: SpendPolicy
    baseline_offer_id: str
    baseline_label: str


# ---- logistics ----

class OptionEval(BaseModel):
    offer: Offer
    status: OptionStatus
    departure: Optional[AwareDatetime] = None
    arrival: Optional[AwareDatetime] = None
    margin_h: Optional[float] = None
    on_time: bool = False
    eta_plausible: bool = True
    price_gbp: Optional[float] = None
    cost_if_used_gbp: Optional[float] = None
    expected_cost_gbp: Optional[float] = None
    co2e_kg: Optional[float] = None
    co2e_note: str = ""
    dedicated_km: float = 0.0
    dedicated_cross_border_trip: bool = False
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---- payments (SolvaPay-style buyer account, simulated) ----

class PolicyDecision(BaseModel):
    status: Literal["allowed", "needs_approval", "denied"]
    reasons: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    approval_id: str
    kind: Literal["hold", "transport"] = "hold"
    hold_id: Optional[str] = None  # set for kind == "transport"
    agent_id: str
    owner: str
    offer_id: str
    merchant: str
    amount_gbp: float
    purpose: str
    reason: str
    policy_reasons: list[str] = Field(default_factory=list)
    what_for: str = ""
    not_included: str = ""
    cancellation: str = ""
    status: Literal["pending", "approved", "declined"] = "pending"
    created_at: AwareDatetime
    decided_at: Optional[AwareDatetime] = None
    decided_by: Optional[str] = None


class Hold(BaseModel):
    hold_id: str
    offer_id: str
    merchant: str
    amount_gbp: float
    what_for: str = ""
    status: Literal["held", "released", "used"] = "held"
    created_at: AwareDatetime
    receipt_id: Optional[str] = None
    confirmation_ref: Optional[str] = None


class Receipt(BaseModel):
    receipt_id: str
    kind: Literal["hold", "transport"] = "hold"
    hold_id: Optional[str] = None
    approval_id: Optional[str] = None
    payer: str
    agent_id: str
    card: str
    payee: str
    amount_gbp: float
    paid_for: str
    not_included: str = ""
    authorisation: str
    cancellation: str = ""
    issued_at: AwareDatetime
    simulated: bool = True


class LedgerEntry(BaseModel):
    at: datetime
    kind: str
    detail: str
    amount_gbp: Optional[float] = None
