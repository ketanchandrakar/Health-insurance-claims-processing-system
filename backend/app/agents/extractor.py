"""Extraction — vision LLM with a fixture-injection seam.

Contract:
  extract(doc: DocumentInput, fixture: dict | None = None) -> ExtractedDoc
If `fixture` is provided (eval path), return it deterministically. Otherwise
call Gemini 2.5 Flash-Lite on doc.content_b64 with structured JSON output.
Low doc_confidence (< 0.5) -> status=UNREADABLE, field values are not trusted.
Raises ExtractionError on hard failure (timeout, malformed response); the
orchestrator catches it and degrades gracefully.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os

from app.models import DocumentInput, DocumentType, ExtractedDoc, ExtractedDocStatus


class ExtractionError(RuntimeError):
    pass


_CONFIDENCE_UNREADABLE = 0.5

_EXTRACTION_PROMPT = """Extract the following fields from this medical document image.
Return ONLY a valid JSON object with these keys:
- patient_name: full name of the patient (string or null)
- diagnosis: medical diagnosis or condition (string or null)
- treatment_date: date of treatment in YYYY-MM-DD format (string or null)
- doctor_name: name of the treating doctor (string or null)
- doctor_reg_no: doctor's registration/license number (string or null)
- total_amount: total bill amount as a number (number or null)
- doc_confidence: your confidence that the document is readable and fields are accurate, from 0.0 (unreadable) to 1.0 (perfectly clear)
- line_items: array of objects with keys "description" (string) and "amount" (number)

If a field is not visible or not applicable, set it to null.
Set doc_confidence < 0.5 if the document is too blurry, damaged, or low-resolution to reliably extract data.
"""


def extract(doc: DocumentInput, fixture: dict | None = None) -> ExtractedDoc:
    # Eval path: return fixture deterministically without calling the LLM
    if fixture is not None:
        return ExtractedDoc.model_validate(fixture)

    if not doc.content_b64:
        raise ExtractionError(
            f"No document content for '{doc.file_name}' and no fixture provided"
        )

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GEMINI_API_KEY")
    if not api_key:
        raise ExtractionError(
            "Neither GOOGLE_API_KEY nor GOOGLE_GEMINI_API_KEY is set — cannot call Gemini"
        )

    return _call_gemini(doc, api_key)


def _call_gemini(doc: DocumentInput, api_key: str) -> ExtractedDoc:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ExtractionError("google-generativeai package not installed") from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    image_bytes = base64.b64decode(doc.content_b64)
    mime_type = mimetypes.guess_type(doc.file_name)[0] or "image/jpeg"
    image_part = {"mime_type": mime_type, "data": image_bytes}

    try:
        response = model.generate_content(
            [image_part, _EXTRACTION_PROMPT],
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            ),
        )
        raw: dict = json.loads(response.text)
    except Exception as exc:
        raise ExtractionError(f"Gemini call failed for '{doc.file_name}': {exc}") from exc

    raw["file_id"] = doc.file_id
    raw["doc_type"] = (doc.actual_type or DocumentType.UNKNOWN).value

    doc_confidence = float(raw.get("doc_confidence") or 0.0)
    raw["doc_confidence"] = doc_confidence
    if doc_confidence < _CONFIDENCE_UNREADABLE:
        raw["status"] = ExtractedDocStatus.UNREADABLE.value
        raw["patient_name"] = None
        raw["diagnosis"] = None
        raw["line_items"] = []
        raw["total_amount"] = None
    else:
        raw.setdefault("status", ExtractedDocStatus.OK.value)
        # Gemini sometimes returns null for a line item amount; drop those rows
        # rather than failing validation (LineItem.amount is a required float).
        raw["line_items"] = [
            item for item in raw.get("line_items") or []
            if item.get("amount") is not None
        ]

    return ExtractedDoc.model_validate(raw)
