"""Intake validation (no LLM, pure function).

Contract:
  validate(claim, policy) -> ValidationResult
Checks: member exists, policy active, treatment within submission deadline,
claimed_amount >= minimum. Failure is data (ValidationResult.ok=False), not
an exception.
"""
from datetime import date as _date

from app.models import ClaimRequest, RejectionReason, ValidationResult
from app.policy import Policy


def validate(
    claim: ClaimRequest,
    policy: Policy,
    today: _date | None = None,
) -> ValidationResult:
    if today is None:
        today = _date.today()

    failures: list[RejectionReason] = []

    if not policy.is_active():
        failures.append(RejectionReason.POLICY_INACTIVE)

    if policy.get_member(claim.member_id) is None:
        failures.append(RejectionReason.MEMBER_NOT_FOUND)

    days_since = (today - claim.treatment_date).days
    if days_since > policy.submission_deadline_days:
        failures.append(RejectionReason.SUBMISSION_DEADLINE_PASSED)

    if claim.claimed_amount < policy.minimum_claim_amount:
        failures.append(RejectionReason.BELOW_MINIMUM_AMOUNT)

    if failures:
        return ValidationResult(
            ok=False,
            failures=failures,
            message="; ".join(r.value for r in failures),
        )
    return ValidationResult(ok=True)
