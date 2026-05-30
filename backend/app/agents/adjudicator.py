"""Adjudication engine (no LLM, deterministic — the heart of the system).

Contract:
  adjudicate(docs, claim, policy) -> AdjudicationResult

Guard order (first failing guard is the rejection reason):
  1. waiting period   (join_date + condition days vs treatment_date)  TC005
  2. exclusion        (diagnosis in policy exclusions)                 TC012
  3. pre-authorization(high-value MRI/CT without pre-auth)             TC007
  4. per-claim limit  (claimed > per_claim_limit)                      TC008

If all guards pass, classify line items (COVERED/EXCLUDED) -> APPROVED /
PARTIAL / REJECTED (TC006), then compute money IN THIS ORDER:
  discounted = amount * (1 - network_discount)   # network hospital only (TC010)
  approved   = discounted * (1 - copay)
  approved   = min(approved, sub_limit)
Each step is appended to calc_trace so the breakdown is reconstructable.
"""
from app.models import AdjudicationResult, ClaimRequest, DecisionStatus, ExtractedDoc
from app.policy import Policy


def adjudicate(
    docs: list[ExtractedDoc],
    claim: ClaimRequest,
    policy: Policy,
) -> AdjudicationResult:
    # stub — guards implemented in Commit 5, financial calc in Commit 6
    return AdjudicationResult(
        decision=DecisionStatus.APPROVED,
        approved_amount=claim.claimed_amount,
    )
