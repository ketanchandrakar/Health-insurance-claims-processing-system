"""Adjudication engine (no LLM, deterministic — the heart of the system).

Contract:
  adjudicate(docs, claim, policy) -> AdjudicationResult

Guard order (first failing guard is the rejection reason):
  1. waiting period   (join_date + condition days vs treatment_date)  TC005
  2. exclusion        (diagnosis in policy exclusions)                 TC012
  3. pre-authorization(high-value DIAGNOSTIC without pre-auth)         TC007
  4. per-claim limit  (claimed > per_claim_limit)                      TC008

If all guards pass, classify line items (COVERED/EXCLUDED) -> APPROVED /
PARTIAL / REJECTED (TC006), then compute money IN THIS ORDER:
  discounted = covered_total * (1 - network_discount)   # network only (TC010)
  approved   = discounted * (1 - copay)
Sub-limits are annual aggregates (DECISIONS.md D2) — not applied per-claim.
Each step is appended to calc_trace so the breakdown is reconstructable.
"""
from datetime import date as _date

from app.models import (
    AdjudicationResult,
    CalcStep,
    ClaimCategory,
    ClaimRequest,
    DecisionStatus,
    DocumentType,
    ExtractedDoc,
    LineItem,
    LineItemClassification,
    RejectionReason,
)
from app.policy import Policy

# Only billing documents carry financial line items.
# Prescriptions, lab reports, and clinical reports provide patient/diagnosis
# context but must not be used as a source of charges — doing so causes
# double-counting when the same procedure appears on both the clinical report
# and the hospital bill.
_BILLING_DOC_TYPES = {DocumentType.HOSPITAL_BILL, DocumentType.PHARMACY_BILL}


def _classify_line_item(
    description: str,
    category: ClaimCategory,
    policy: Policy,
) -> tuple[LineItemClassification, str | None]:
    """Return (classification, reason_str)."""
    desc = description.lower()

    covered_list = policy.covered_services_for_category(category)
    excluded_list = policy.excluded_services_for_category(category)

    if covered_list or excluded_list:
        # DENTAL / VISION: check category-specific procedure lists
        for svc in excluded_list:
            if svc.lower() in desc:
                return LineItemClassification.EXCLUDED, f"Not covered: {svc}"
        for svc in covered_list:
            if svc.lower() in desc:
                return LineItemClassification.COVERED, None
        return LineItemClassification.UNKNOWN, None
    else:
        # Other categories: fall back to global policy exclusions
        if policy.is_excluded(description):
            return LineItemClassification.EXCLUDED, "Excluded under policy terms"
        return LineItemClassification.COVERED, None


def adjudicate(
    docs: list[ExtractedDoc],
    claim: ClaimRequest,
    policy: Policy,
    today: _date | None = None,
) -> AdjudicationResult:
    if today is None:
        today = _date.today()

    diagnosis = next((d.diagnosis for d in docs if d.diagnosis), None)
    member = policy.get_member(claim.member_id)

    # ------------------------------------------------------------------
    # Guard 1 — waiting period
    # ------------------------------------------------------------------
    if member:
        eligible = policy.eligible_from_date(member, diagnosis)
        if eligible > claim.treatment_date:
            return AdjudicationResult(
                decision=DecisionStatus.REJECTED,
                reasons=[RejectionReason.WAITING_PERIOD],
                eligible_from=eligible,
                notes=f"Eligible from {eligible.isoformat()}",
            )

    # ------------------------------------------------------------------
    # Guard 2 — excluded condition
    # ------------------------------------------------------------------
    if policy.is_excluded(diagnosis):
        return AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.EXCLUDED_CONDITION],
            notes=f"Diagnosis '{diagnosis}' is excluded under the policy",
        )

    # ------------------------------------------------------------------
    # Guard 3 — pre-authorization (DIAGNOSTIC category only)
    # ------------------------------------------------------------------
    if claim.claim_category == ClaimCategory.DIAGNOSTIC:
        threshold = policy.pre_auth_threshold
        if claim.claimed_amount >= threshold and not claim.pre_auth_number:
            return AdjudicationResult(
                decision=DecisionStatus.REJECTED,
                reasons=[RejectionReason.PRE_AUTH_MISSING],
                notes=f"Pre-authorization required for DIAGNOSTIC claims ≥ ₹{threshold:,.0f}",
            )

    # ------------------------------------------------------------------
    # Guard 4 — per-claim limit
    # Categories with explicit procedure lists (DENTAL, VISION) are gated
    # by their own sub-limit via classification; skip this guard for them.
    # ------------------------------------------------------------------
    has_explicit_list = bool(policy.covered_services_for_category(claim.claim_category))
    limit = policy.per_claim_limit
    if not has_explicit_list and claim.claimed_amount > limit:
        return AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.PER_CLAIM_EXCEEDED],
            notes=(
                f"Claimed ₹{claim.claimed_amount:,.0f} exceeds "
                f"per-claim limit of ₹{limit:,.0f}"
            ),
        )

    # ------------------------------------------------------------------
    # All guards passed — classify line items (billing docs only)
    # ------------------------------------------------------------------
    classified: list[LineItem] = []
    for doc in docs:
        if doc.doc_type not in _BILLING_DOC_TYPES:
            continue
        for raw in doc.line_items:
            cls, reason = _classify_line_item(raw.description, claim.claim_category, policy)
            classified.append(LineItem(
                description=raw.description,
                amount=raw.amount,
                classification=cls,
                reason=reason,
            ))

    covered = [li for li in classified if li.classification == LineItemClassification.COVERED]
    excluded = [li for li in classified if li.classification == LineItemClassification.EXCLUDED]

    if classified and not covered:
        return AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.NOT_COVERED],
            line_item_breakdown=classified,
            notes="No line items were covered under the policy",
        )

    decision = DecisionStatus.PARTIAL if excluded else DecisionStatus.APPROVED
    base = sum(li.amount for li in covered) if covered else claim.claimed_amount

    # ------------------------------------------------------------------
    # Financial calculation — network discount → co-pay (in this order)
    # Sub-limits are annual aggregates and are NOT applied per claim
    # ------------------------------------------------------------------
    calc_trace: list[CalcStep] = []

    is_network = policy.is_network_hospital(claim.hospital_name)
    disc_rate = policy.network_discount_for_category(claim.claim_category) if is_network else 0.0
    discounted = base * (1 - disc_rate)
    calc_trace.append(CalcStep(
        label=f"Network discount ({disc_rate * 100:.0f}%)",
        amount=round(discounted, 2),
    ))

    copay_rate = policy.copay_for_category(claim.claim_category)
    approved = discounted * (1 - copay_rate)
    calc_trace.append(CalcStep(
        label=f"Co-pay ({copay_rate * 100:.0f}%)",
        amount=round(approved, 2),
    ))

    return AdjudicationResult(
        decision=decision,
        approved_amount=round(approved, 2),
        line_item_breakdown=classified,
        calc_trace=calc_trace,
    )
