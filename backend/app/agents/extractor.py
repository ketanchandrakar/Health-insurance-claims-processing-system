"""Extraction — vision LLM with a fixture-injection seam.

Contract:
  extract(doc: DocumentInput, fixture: dict | None = None) -> ExtractedDoc
If `fixture` is provided (eval path), return it deterministically. Otherwise
call the vision model on doc.content_b64 with a strict structured-output
schema and per-field confidence. Low doc_confidence -> status=UNREADABLE.
Raises ExtractionError on hard failure (timeout, malformed response); the
orchestrator catches it and degrades.

Run per-document calls in parallel with concurrent.futures.ThreadPoolExecutor
(Flask views are sync; the LLM calls are I/O-bound).
"""
from app.models import DocumentInput, DocumentType, ExtractedDoc, ExtractedDocStatus


class ExtractionError(RuntimeError):
    pass


def extract(doc: DocumentInput, fixture: dict | None = None) -> ExtractedDoc:
    if fixture is not None:
        return ExtractedDoc.model_validate(fixture)

    # yet to implement
    return ExtractedDoc(
        file_id=doc.file_id,
        doc_type=doc.actual_type or DocumentType.UNKNOWN,
        doc_confidence=0.9,
        status=ExtractedDocStatus.OK,
    )
