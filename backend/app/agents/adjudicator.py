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
  discounted = amount * (1 - network_discount)   # network hospital only (TC010)
  approved   = discounted * (1 - copay)
  approved   = min(approved, sub_limit)
Each step is appended to calc_trace so the breakdown is reconstructable.
Line item classification and financial calc to be added.
"""
from datetime import date as _date

from app.models import (
    AdjudicationResult,
    ClaimCategory,
    ClaimRequest,
    DecisionStatus,
    ExtractedDoc,
    RejectionReason,
)
from app.policy import Policy


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

    # Guard 1 — waiting period
    if member:
        eligible = policy.eligible_from_date(member, diagnosis)
        if eligible > claim.treatment_date:
            return AdjudicationResult(
                decision=DecisionStatus.REJECTED,
                reasons=[RejectionReason.WAITING_PERIOD],
                eligible_from=eligible,
                notes=f"Eligible from {eligible.isoformat()}",
            )

    # Guard 2 — excluded condition
    if policy.is_excluded(diagnosis):
        return AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.EXCLUDED_CONDITION],
            notes=f"Diagnosis '{diagnosis}' is excluded under the policy",
        )

    # Guard 3 — pre-authorization (DIAGNOSTIC category only)
    if claim.claim_category == ClaimCategory.DIAGNOSTIC:
        threshold = policy.pre_auth_threshold
        if claim.claimed_amount >= threshold:
            return AdjudicationResult(
                decision=DecisionStatus.REJECTED,
                reasons=[RejectionReason.PRE_AUTH_MISSING],
                notes=f"Pre-authorization required for DIAGNOSTIC claims ≥ ₹{threshold:,.0f}",
            )

    # Guard 4 — per-claim limit
    limit = policy.per_claim_limit
    if claim.claimed_amount > limit:
        return AdjudicationResult(
            decision=DecisionStatus.REJECTED,
            reasons=[RejectionReason.PER_CLAIM_EXCEEDED],
            notes=(
                f"Claimed ₹{claim.claimed_amount:,.0f} exceeds "
                f"per-claim limit of ₹{limit:,.0f}"
            ),
        )

    # All guards passed — line item classification + financial calc to be added
    return AdjudicationResult(
        decision=DecisionStatus.APPROVED,
        approved_amount=claim.claimed_amount,
    )
