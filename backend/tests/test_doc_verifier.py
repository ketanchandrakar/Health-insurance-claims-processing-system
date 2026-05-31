"""Tests for agents.doc_verifier — Gate 1 document type verification."""
import pytest

from app.agents.doc_verifier import verify_documents
from app.models import ClaimCategory, DocCheckResult, DocumentType
from app.policy import load_policy


@pytest.fixture(scope="module")
def policy():
    return load_policy()


def test_tc001_wrong_document_type(policy):
    # TC001: CONSULTATION requires PRESCRIPTION + HOSPITAL_BILL
    # Member uploaded two PRESCRIPTIONs — HOSPITAL_BILL is missing
    uploaded = [DocumentType.PRESCRIPTION, DocumentType.PRESCRIPTION]
    result = verify_documents(uploaded, ClaimCategory.CONSULTATION, policy, [])

    assert result.passed is False
    assert DocumentType.HOSPITAL_BILL in result.missing_types
    # Message must name both what was uploaded AND what is required
    assert "PRESCRIPTION" in result.message
    assert "HOSPITAL_BILL" in result.message


def test_tc002_unreadable_document(policy):
    # TC002: PHARMACY requires PRESCRIPTION + PHARMACY_BILL
    # Both types are present but PHARMACY_BILL (F004) is unreadable
    uploaded = [DocumentType.PRESCRIPTION, DocumentType.PHARMACY_BILL]
    result = verify_documents(uploaded, ClaimCategory.PHARMACY, policy, ["F004"])

    assert result.passed is False
    assert "F004" in result.unreadable_files
    assert result.message is not None
    assert "F004" in result.message  # message must name the specific file


def test_all_required_docs_present(policy):
    # Clean path: CONSULTATION with both required types uploaded
    uploaded = [DocumentType.PRESCRIPTION, DocumentType.HOSPITAL_BILL]
    result = verify_documents(uploaded, ClaimCategory.CONSULTATION, policy, [])
    assert result.passed is True
    assert result.missing_types == []
    assert result.unreadable_files == []


def test_partial_missing_one_required(policy):
    # DIAGNOSTIC requires PRESCRIPTION + LAB_REPORT + HOSPITAL_BILL
    # Only PRESCRIPTION + LAB_REPORT uploaded — HOSPITAL_BILL missing
    uploaded = [DocumentType.PRESCRIPTION, DocumentType.LAB_REPORT]
    result = verify_documents(uploaded, ClaimCategory.DIAGNOSTIC, policy, [])

    assert result.passed is False
    assert DocumentType.HOSPITAL_BILL in result.missing_types
    assert DocumentType.PRESCRIPTION not in result.missing_types
    assert DocumentType.LAB_REPORT not in result.missing_types
