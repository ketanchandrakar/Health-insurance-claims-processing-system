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
    required = policy.required_documents(category)
    uploaded_set = set(uploaded_types)
    missing = [t for t in required if t not in uploaded_set]

    if not missing and not unreadable_ids:
        return DocCheckResult(passed=True)

    messages: list[str] = []

    if missing:
        # TC001: message must name what was uploaded AND what is required
        uploaded_str = ", ".join(t.value for t in uploaded_types) if uploaded_types else "no documents"
        required_str = " and ".join(t.value for t in required)
        missing_str = ", ".join(t.value for t in missing)
        messages.append(
            f"You uploaded {uploaded_str}. "
            f"This {category.value} claim requires {required_str}. "
            f"Please also upload: {missing_str}."
        )

    if unreadable_ids:
        # TC002: one specific message per unreadable file so member knows exactly what to re-upload
        for fid in unreadable_ids:
            messages.append(f"File '{fid}' could not be read. Please re-upload a clear copy.")

    return DocCheckResult(
        passed=False,
        missing_types=missing,
        unreadable_files=unreadable_ids,
        message=" ".join(messages),
    )
