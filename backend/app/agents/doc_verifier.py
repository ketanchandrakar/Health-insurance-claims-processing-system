"""Gate 1 — document verification.

Contract:
  verify_documents(uploaded_types, category, policy, unreadable_ids) -> DocCheckResult
Compares uploaded document types against policy.required_documents(category).
On failure, builds a SPECIFIC member-facing message naming the uploaded type
and the required type (TC001). Flags unreadable files for re-upload (TC002).
"""
from app.models import ClaimCategory, DocCheckResult, DocumentType
from app.policy import Policy


def verify_documents(
    uploaded_types: list[DocumentType],
    category: ClaimCategory,
    policy: Policy,
    unreadable_ids: list[str],
) -> DocCheckResult:
    # yet to implement
    return DocCheckResult(passed=True)
