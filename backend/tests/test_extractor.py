"""Tests for agents.extractor — fixture seam and error paths.

The real Gemini call is not tested here (requires API key + network).
The eval runner exercises the fixture seam for all 12 TCs.
"""
import pytest

from app.agents.extractor import ExtractionError, extract
from app.models import DocumentInput, DocumentType, ExtractedDocStatus


def _doc(file_id: str = "F001", file_name: str = "test.jpg", content_b64: str | None = None) -> DocumentInput:
    return DocumentInput(
        file_id=file_id,
        file_name=file_name,
        actual_type=DocumentType.HOSPITAL_BILL,
        content_b64=content_b64,
    )


def test_fixture_seam_returns_exact_doc():
    fixture = {
        "file_id": "F001",
        "doc_type": "HOSPITAL_BILL",
        "patient_name": "Rajesh Kumar",
        "diagnosis": "Viral Fever",
        "line_items": [],
        "total_amount": 1500.0,
        "treatment_date": "2024-11-01",
        "doc_confidence": 0.95,
        "status": "OK",
    }
    result = extract(_doc(), fixture=fixture)
    assert result.patient_name == "Rajesh Kumar"
    assert result.diagnosis == "Viral Fever"
    assert result.doc_confidence == 0.95
    assert result.status == ExtractedDocStatus.OK


def test_no_content_and_no_fixture_raises():
    with pytest.raises(ExtractionError):
        extract(_doc(content_b64=None))


def test_low_confidence_fixture_marked_unreadable():
    # TC002: blurry doc has doc_confidence 0.15 → status must be UNREADABLE in fixture
    fixture = {
        "file_id": "F004",
        "doc_type": "PHARMACY_BILL",
        "patient_name": None,
        "doc_confidence": 0.15,
        "status": "UNREADABLE",
    }
    result = extract(_doc(file_id="F004"), fixture=fixture)
    assert result.status == ExtractedDocStatus.UNREADABLE
    assert result.patient_name is None
