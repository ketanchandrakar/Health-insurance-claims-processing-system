"""Intake validation (no LLM, pure function).

Contract:
  validate(claim, policy) -> ValidationResult
Checks: member exists, policy active, treatment within submission deadline,
claimed_amount >= minimum. Failure is data (ValidationResult.ok=False), not
an exception.
"""
from app.models import ClaimRequest, ValidationResult
from app.policy import Policy


def validate(claim: ClaimRequest, policy: Policy) -> ValidationResult:
    # stub — real implementation in Commit 4
    return ValidationResult(ok=True)
