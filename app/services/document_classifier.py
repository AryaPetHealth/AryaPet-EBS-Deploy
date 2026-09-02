"""Turns a Textract analyze_document response into a structured "card" for a
document, shaped differently depending on what kind of document it is.

This is a first-pass heuristic classifier (keyword + table-shape based), not ML -
it will misclassify or under-extract on lab report layouts and vet note styles it
hasn't seen. If extraction quality matters more than staying AWS-native, replacing
this with an LLM-based classify+extract pass is a reasonable upgrade path; the
Document.parsed_result JSONB shape here would stay compatible either way.
"""

import re
from typing import Any, Literal

DocumentType = Literal["lab_report", "vet_visit", "unknown"]

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
    "clinic",
    "veterinarian",
    "treatment plan",
    "physical exam",
    "vaccination",
    "presenting complaint",
)

_DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)


def extract_text_and_tables(textract_response: dict[str, Any]) -> tuple[str, list[list[list[str]]]]:
    """Returns (full_text, tables) where each table is a list of rows of cell text,
    pulled from a Textract analyze_document response's Blocks."""
    blocks = textract_response.get("Blocks", [])
    blocks_by_id = {b["Id"]: b for b in blocks}

    lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
    full_text = "\n".join(lines)

    tables: list[list[list[str]]] = []
    for block in blocks:
        if block.get("BlockType") != "TABLE":
            continue
        cells_by_position: dict[tuple[int, int], str] = {}
        max_row = 0
        for rel in block.get("Relationships", []):
            if rel.get("Type") != "CHILD":
                continue
            for cell_id in rel.get("Ids", []):
                cell = blocks_by_id.get(cell_id)
                if cell is None or cell.get("BlockType") != "CELL":
                    continue
                row_index = cell.get("RowIndex", 1)
                col_index = cell.get("ColumnIndex", 1)
                max_row = max(max_row, row_index)
                cell_text = _cell_text(cell, blocks_by_id)
                cells_by_position[(row_index, col_index)] = cell_text

        max_col = max((c for _, c in cells_by_position), default=0)
        table_rows = [
            [cells_by_position.get((r, c), "") for c in range(1, max_col + 1)]
            for r in range(1, max_row + 1)
        ]
        tables.append(table_rows)

    return full_text, tables


def _cell_text(cell: dict[str, Any], blocks_by_id: dict[str, Any]) -> str:
    words = []
    for rel in cell.get("Relationships", []):
        if rel.get("Type") != "CHILD":
            continue
        for word_id in rel.get("Ids", []):
            word = blocks_by_id.get(word_id)
            if word is not None and word.get("Text"):
                words.append(word["Text"])
    return " ".join(words)


def classify_document(text: str, tables: list[list[list[str]]]) -> DocumentType:
    lower_text = text.lower()
    has_lab_keyword = any(keyword in lower_text for keyword in _LAB_KEYWORDS)
    has_vet_keyword = any(keyword in lower_text for keyword in _VET_VISIT_KEYWORDS)

    if tables and has_lab_keyword:
        return "lab_report"
    if has_vet_keyword:
        return "vet_visit"
    return "unknown"


def _first_date(text: str) -> str | None:
    match = _DATE_PATTERN.search(text)
    return match.group(0) if match else None


def build_lab_report_card(text: str, tables: list[list[list[str]]]) -> dict[str, Any]:
    test_results: list[dict[str, str]] = []
    for table in tables:
        for row in table:
            # Skip header-shaped rows and rows without at least a name + one value.
            if len(row) < 2 or not row[0] or row[0].strip().lower() in ("test", "test name", "parameter"):
                continue
            name, *rest = (cell.strip() for cell in row)
            if not name or not any(rest):
                continue
            test_results.append(
                {
                    "name": name,
                    "value": rest[0] if len(rest) > 0 else "",
                    "unit": rest[1] if len(rest) > 1 else "",
                    "reference_range": rest[2] if len(rest) > 2 else "",
                }
            )

    return {
        "type": "lab_report",
        "collection_date": _first_date(text),
        "test_results": test_results,
    }


def build_vet_visit_card(text: str) -> dict[str, Any]:
    return {
        "type": "vet_visit",
        "visit_date": _first_date(text),
        "diagnosis": _line_after_keyword(text, "diagnosis"),
        "treatment_plan": (
            _line_after_keyword(text, "treatment plan") or _line_after_keyword(text, "treatment")
        ),
    }


def _line_after_keyword(text: str, keyword: str) -> str | None:
    for line in text.splitlines():
        lower_line = line.lower()
        if keyword in lower_line:
            idx = lower_line.index(keyword) + len(keyword)
            remainder = line[idx:].lstrip(" :-\t")
            if remainder:
                return remainder
    return None


def build_unknown_card(text: str) -> dict[str, Any]:
    return {"type": "unknown", "raw_text": text}


def build_document_card(text: str, tables: list[list[list[str]]]) -> dict[str, Any]:
    document_type = classify_document(text, tables)
    if document_type == "lab_report":
        return build_lab_report_card(text, tables)
    if document_type == "vet_visit":
        return build_vet_visit_card(text)
    return build_unknown_card(text)
