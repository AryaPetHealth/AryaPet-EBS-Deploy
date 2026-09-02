"""Classifies client-submitted OCR text and extracts a structured "card" from it,
using a self-hosted spaCy pipeline (en_core_web_sm) - lightweight enough to run
alongside the API on a t3.micro, unlike the transformer-based approach this replaced.

spaCy's small model has no zero-shot classification or medical NER, so:
- Classification is keyword-based (same idea as the very first Textract-era version
  of this module), matched against spaCy's lemmatized tokens rather than raw
  substrings - catches "diagnosed"/"diagnosis" alike, for example.
- Field extraction uses spaCy's built-in generic NER (DATE/ORG/PERSON) plus
  keyword-anchored sentence lookup (via doc.sents) for fields with no generic
  entity type, like diagnosis/treatment_plan.

This remains a first-pass heuristic, not a trained clinical NLP model - a lab report
with many distinct test rows will only get its most prominent one captured reliably,
since flattened OCR text loses the table structure needed to reconstruct a full panel.

The spaCy pipeline is loaded once per process (lazily, via lru_cache) since loading
is comparatively expensive - see app/workers/processing_consumer.py, the only caller.
"""

from functools import lru_cache
from typing import Any, Literal

DocumentType = Literal["lab_report", "vet_visit", "unknown"]

_SPACY_MODEL = "en_core_web_sm"

_LAB_KEYWORDS = (
    "reference range",
    "specimen",
    "cbc",
    "wbc",
    "rbc",
    "hematology",
    "biochemistry",
    "test result",
    "panel",
)

_VET_VISIT_KEYWORDS = (
    "diagnosis",
    "diagnose",
    "clinic",
    "veterinarian",
    "treatment plan",
    "treatment",
    "physical exam",
    "vaccination",
    "presenting complaint",
)


@lru_cache(maxsize=1)
def _nlp() -> Any:
    import spacy

    return spacy.load(_SPACY_MODEL)


def _lemmatized_text(text: str) -> tuple[Any, str]:
    doc = _nlp()(text)
    lemmas = " ".join(token.lemma_.lower() for token in doc)
    return doc, lemmas


def classify_document(text: str) -> DocumentType:
    if not text.strip():
        return "unknown"

    _, lemmas = _lemmatized_text(text)
    has_lab_keyword = any(keyword in lemmas for keyword in _LAB_KEYWORDS)
    has_vet_keyword = any(keyword in lemmas for keyword in _VET_VISIT_KEYWORDS)

    if has_lab_keyword:
        return "lab_report"
    if has_vet_keyword:
        return "vet_visit"
    return "unknown"


def _first_entity(doc: Any, label: str) -> str | None:
    for ent in doc.ents:
        if ent.label_ == label:
            return ent.text
    return None


def _sentence_containing(doc: Any, *keywords: str) -> str | None:
    for sent in doc.sents:
        lower_sent = sent.text.lower()
        if any(keyword in lower_sent for keyword in keywords):
            return sent.text.strip()
    return None


def build_lab_report_card(text: str) -> dict[str, Any]:
    doc = _nlp()(text)
    return {
        "type": "lab_report",
        "collection_date": _first_entity(doc, "DATE"),
        "test_result": _sentence_containing(doc, "test", "result", "panel"),
    }


def build_vet_visit_card(text: str) -> dict[str, Any]:
    doc = _nlp()(text)
    return {
        "type": "vet_visit",
        "visit_date": _first_entity(doc, "DATE"),
        "clinic_name": _first_entity(doc, "ORG"),
        "diagnosis": _sentence_containing(doc, "diagnosis", "diagnosed"),
        "treatment_plan": _sentence_containing(doc, "treatment"),
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
