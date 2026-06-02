"""
Domain models — the contracts every component speaks.

Freeze these first. Every agent signature, every test, and the React props
derive from the types defined here. Implementations fill in *behind* these
interfaces; the interfaces themselves should not need to change as the build
progresses.

Read order for a new engineer:
  ClaimRequest      -> what comes in from the frontend
  ExtractedDoc      -> what the vision extractor produces per document
  *Result models    -> what each agent hands back to the orchestrator
  TraceEvent        -> one row of the explainability trace
  Decision          -> what goes back to the frontend (always, even on failure)
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    PHARMACY_BILL = "PHARMACY_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    # Early exit before adjudication ever ran (document problem). Distinct from
    # REJECTED so the UI and ops can tell "we never decided" from "we said no".
    STOPPED = "STOPPED"


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"               # TC005
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"        # TC012
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"            # TC007
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"        # TC008
    ANNUAL_LIMIT_EXCEEDED = "ANNUAL_LIMIT_EXCEEDED"
    NOT_COVERED = "NOT_COVERED"
    SUBMISSION_DEADLINE_PASSED = "SUBMISSION_DEADLINE_PASSED"
    BELOW_MINIMUM_AMOUNT = "BELOW_MINIMUM_AMOUNT"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    POLICY_INACTIVE = "POLICY_INACTIVE"


class ExtractedDocStatus(str, Enum):
    OK = "OK"                 # all key fields read with acceptable confidence
    PARTIAL = "PARTIAL"       # some fields unreadable, doc still usable
    UNREADABLE = "UNREADABLE" # too degraded to trust — ask for re-upload (TC002)


class LineItemClassification(str, Enum):
    COVERED = "COVERED"
    EXCLUDED = "EXCLUDED"
    UNKNOWN = "UNKNOWN"


class TraceStatus(str, Enum):
    OK = "OK"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    DEGRADED = "DEGRADED"


# ---------------------------------------------------------------------------
# Inbound request (frontend -> POST /claims/evaluate)
# ---------------------------------------------------------------------------

class DocumentInput(BaseModel):
    file_id: str
    file_name: str
    # The eval cases provide the ground-truth document type. Real uploads from
    # the UI leave this None and rely on the extractor to detect the type.
    actual_type: DocumentType | None = None
    # Base64-encoded bytes (image or PDF) for real uploads. None in the eval
    # path, where extraction is served from a fixture instead.
    content_b64: str | None = None


class ClaimRequest(BaseModel):
    member_id: str
    policy_id: str
    claim_category: ClaimCategory
    treatment_date: date
    claimed_amount: float
    documents: list[DocumentInput]

    # Optional context some test cases supply.
    hospital_name: str | None = None          # network-discount check (TC010)
    pre_auth_number: str | None = None        # pre-authorisation reference (TC007)
    ytd_claims_amount: float = 0.0            # annual-limit check
    claims_history: list[dict] = Field(default_factory=list)  # fraud check (TC009)

    # TC011 hook: deterministically force one component to fail so we can prove
    # the pipeline degrades gracefully instead of crashing.
    simulate_component_failure: bool = False


# ---------------------------------------------------------------------------
# Extraction output (one per document)
# ---------------------------------------------------------------------------

class LineItem(BaseModel):
    description: str
    amount: float
    classification: LineItemClassification = LineItemClassification.UNKNOWN
    # Why this line was covered/excluded — surfaced at the line level (TC006).
    reason: str | None = None


class ExtractedDoc(BaseModel):
    file_id: str
    doc_type: DocumentType
    patient_name: str | None = None
    diagnosis: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    total_amount: float | None = None
    treatment_date: date | None = None
    doctor_name: str | None = None
    doctor_reg_no: str | None = None
    # Per-field confidence in [0, 1]; lets us flag fields hidden by stamps etc.
    field_confidences: dict[str, float] = Field(default_factory=dict)
    doc_confidence: float = 0.0
    status: ExtractedDocStatus = ExtractedDocStatus.OK


# ---------------------------------------------------------------------------
# Intermediate agent outputs (agent -> orchestrator)
# ---------------------------------------------------------------------------

class ValidationResult(BaseModel):
    ok: bool
    failures: list[RejectionReason] = Field(default_factory=list)
    message: str | None = None


class DocCheckResult(BaseModel):
    """Gate 1. Failure here STOPS the pipeline before adjudication."""
    passed: bool
    missing_types: list[DocumentType] = Field(default_factory=list)
    wrong_types: list[DocumentType] = Field(default_factory=list)
    unreadable_files: list[str] = Field(default_factory=list)  # file_ids (TC002)
    # Specific, member-facing text naming uploaded vs required types (TC001).
    message: str | None = None


class ConsistencyResult(BaseModel):
    """Gate 2. Failure here STOPS the pipeline."""
    consistent: bool
    # Each mismatch: {"field": "patient_name", "values": ["Rajesh Kumar", "Arjun Mehta"]}
    mismatches: list[dict] = Field(default_factory=list)
    # Soft anomalies that passed but are worth noting (e.g. borderline name score,
    # near-miss date). Synthesizer applies a -0.10 confidence penalty when non-empty.
    warnings: list[str] = Field(default_factory=list)
    message: str | None = None  # names both patients on a mismatch (TC003)


class CalcStep(BaseModel):
    """One line of the money calculation, in the order it was applied."""
    label: str          # e.g. "Network discount (20%)"
    amount: float       # running amount after this step


class AdjudicationResult(BaseModel):
    decision: DecisionStatus
    approved_amount: float | None = None
    line_item_breakdown: list[LineItem] = Field(default_factory=list)
    reasons: list[RejectionReason] = Field(default_factory=list)
    # Ordered: network discount -> co-pay -> sub-limit cap (TC010 depends on order).
    calc_trace: list[CalcStep] = Field(default_factory=list)
    notes: str | None = None
    eligible_from: date | None = None  # waiting-period eligibility date (TC005)


class FraudResult(BaseModel):
    signals: list[str] = Field(default_factory=list)
    # Fraud can only ESCALATE to MANUAL_REVIEW; it never approves or downgrades.
    escalate_to_review: bool = False


# ---------------------------------------------------------------------------
# Trace + final decision (orchestrator -> frontend)
# ---------------------------------------------------------------------------

class TraceEvent(BaseModel):
    component: str
    status: TraceStatus
    summary: str                                  # one-line human-readable
    detail: dict = Field(default_factory=dict)    # structured, machine-readable
    duration_ms: int = 0


class Decision(BaseModel):
    """The single object the ops team reads to reconstruct *why*."""
    status: DecisionStatus
    approved_amount: float | None = None
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    rejection_reasons: list[RejectionReason] = Field(default_factory=list)
    line_item_breakdown: list[LineItem] = Field(default_factory=list)
    recommend_manual_review: bool = False
    # For STOPPED outcomes: the specific, actionable message (TC001/002/003).
    message_to_member: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
