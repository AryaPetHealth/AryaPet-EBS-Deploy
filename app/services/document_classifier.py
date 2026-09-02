"""Classifies client-submitted OCR text and extracts a structured "card" from it,
using self-hosted HuggingFace models (not Textract, not HF's hosted Inference API -
see the plan this was built from for why).

This is a first-pass, question-answering-based extractor, not a trained NER/table
model - it will do reasonably well on prose (vet visit notes) since that's what QA
models are built for, but a lab report with many distinct test rows will only get its
most prominent result captured reliably; flattened OCR text loses the table structure
that would be needed to reconstruct a full test panel. A table-aware model, or asking
the client to preserve structure, is the natural next step if that accuracy matters.

Models are loaded once per process (lazily, via lru_cache) since construction is
expensive - see app/workers/processing_consumer.py, which is the only caller.
"""

from functools import lru_cache
from typing import Any, Literal

DocumentType = Literal["lab_report", "vet_visit", "unknown"]

_CLASSIFICATION_MODEL = "MoritzLaurer/deberta-v3-base-zeroshot-v1"
_QA_MODEL = "deepset/roberta-base-squad2"
_CLASSIFICATION_LABELS = ("lab report", "veterinary visit note")
_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.5
_QA_CONFIDENCE_THRESHOLD = 0.1


@lru_cache(maxsize=1)
def _classification_pipeline() -> Any:
    from transformers import pipeline

    return pipeline("zero-shot-classification", model=_CLASSIFICATION_MODEL)


@lru_cache(maxsize=1)
def _qa_pipeline() -> Any:
    from transformers import pipeline

    return pipeline("question-answering", model=_QA_MODEL)


def classify_document(text: str) -> DocumentType:
    if not text.strip():
        return "unknown"

    result = _classification_pipeline()(text, candidate_labels=list(_CLASSIFICATION_LABELS))
    top_label, top_score = result["labels"][0], result["scores"][0]
    if top_score < _CLASSIFICATION_CONFIDENCE_THRESHOLD:
        return "unknown"

    return "lab_report" if top_label == "lab report" else "vet_visit"


def _answer(text: str, question: str) -> str | None:
    result = _qa_pipeline()(question=question, context=text)
    if result["score"] < _QA_CONFIDENCE_THRESHOLD:
        return None
    return result["answer"]


def build_lab_report_card(text: str) -> dict[str, Any]:
    return {
        "type": "lab_report",
        "collection_date": _answer(text, "What is the collection date?"),
        "test_name": _answer(text, "What test was performed?"),
        "result_value": _answer(text, "What is the result value?"),
    }


def build_vet_visit_card(text: str) -> dict[str, Any]:
    return {
        "type": "vet_visit",
        "visit_date": _answer(text, "What is the visit date?"),
        "clinic_name": _answer(text, "What is the name of the clinic?"),
        "diagnosis": _answer(text, "What is the diagnosis?"),
        "treatment_plan": _answer(text, "What is the treatment plan?"),
    }


def build_unknown_card(text: str) -> dict[str, Any]:
    return {"type": "unknown", "raw_text": text}


def build_document_card(text: str) -> dict[str, Any]:
    document_type = classify_document(text)
    if document_type == "lab_report":
        return build_lab_report_card(text)
    if document_type == "vet_visit":
        return build_vet_visit_card(text)
    return build_unknown_card(text)
