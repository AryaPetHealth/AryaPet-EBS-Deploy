"""Canonicalizes lab analyte names so the same measurement from two labs lines up.

Labs spell the same analyte differently - "ALP", "Alk Phos", "Alkaline Phosphatase",
"S. Alkaline Phosphatase" are one thing. Without normalization a pet's trend for that
analyte silently splits into several unrelated series.

This is a spaCy PhraseMatcher over a hand-maintained alias table rather than a UMLS/
LOINC linker: those are built for human medicine and the linker's knowledge base alone
needs about a gigabyte, where this covers the analytes that actually appear on companion
-animal panels in a few kilobytes. Unknown analytes pass through with their original
name rather than being dropped - an unmapped result is still a result worth storing.
"""

from functools import lru_cache
from typing import Any

# canonical name -> aliases (lowercased; the canonical name itself is matched too).
# Covers the standard companion-animal chemistry, haematology and electrolyte panels.
ANALYTE_ALIASES: dict[str, tuple[str, ...]] = {
    # ── Liver ──
    "Alanine Aminotransferase": ("alt", "sgpt", "alt (sgpt)", "s. alt", "serum alt"),
    "Aspartate Aminotransferase": ("ast", "sgot", "ast (sgot)", "s. ast"),
    "Alkaline Phosphatase": ("alp", "alk phos", "alkaline phosphate", "s. alkaline phosphatase", "sap"),
    "Gamma-Glutamyl Transferase": ("ggt", "gamma gt", "g.g.t"),
    "Total Bilirubin": ("total bilirubin", "bilirubin total", "t. bilirubin", "tbil"),
    "Direct Bilirubin": ("direct bilirubin", "bilirubin direct", "conjugated bilirubin", "dbil"),
    "Indirect Bilirubin": ("indirect bilirubin", "bilirubin indirect", "unconjugated bilirubin"),
    "Albumin": ("albumin", "s. albumin", "alb"),
    "Globulin": ("globulin", "s. globulin", "glob"),
    "Total Protein": ("total protein", "protein total", "t. protein", "tp"),
    "Albumin/Globulin Ratio": ("a/g ratio", "ag ratio", "albumin globulin ratio", "a:g ratio"),
    # ── Kidney ──
    "Creatinine": ("creatinine", "s. creatinine", "creat", "serum creatinine"),
    "Blood Urea": ("blood urea", "urea", "s. urea", "serum urea"),
    "Blood Urea Nitrogen": ("bun", "blood urea nitrogen", "urea nitrogen"),
    "BUN/Creatinine Ratio": ("bun/creatinine ratio", "bun creatinine ratio", "b/c ratio"),
    "Uric Acid": ("uric acid", "s. uric acid"),
    "Symmetric Dimethylarginine": ("sdma", "symmetric dimethylarginine"),
    # ── Electrolytes & minerals ──
    "Sodium": ("sodium", "na", "na+", "s. sodium"),
    "Potassium": ("potassium", "k", "k+", "s. potassium"),
    "Chloride": ("chloride", "cl", "cl-", "s. chloride"),
    "Calcium": ("calcium", "ca", "total calcium", "s. calcium"),
    "Phosphorus": ("phosphorus", "phosphate", "inorganic phosphorus", "po4", "p"),
    "Magnesium": ("magnesium", "mg", "s. magnesium"),
    # ── Metabolic ──
    "Glucose": ("glucose", "blood glucose", "random blood sugar", "rbs", "fasting blood sugar", "fbs"),
    "Cholesterol": ("cholesterol", "total cholesterol", "s. cholesterol"),
    "Triglycerides": ("triglycerides", "tg", "s. triglycerides"),
    "Amylase": ("amylase", "s. amylase"),
    "Lipase": ("lipase", "s. lipase"),
    # ── Haematology ──
    "Haemoglobin": ("haemoglobin", "hemoglobin", "hb", "hgb"),
    "Packed Cell Volume": ("pcv", "packed cell volume", "haematocrit", "hematocrit", "hct"),
    "Red Blood Cell Count": ("rbc", "red blood cell count", "rbc count", "erythrocyte count"),
    "White Blood Cell Count": ("wbc", "white blood cell count", "wbc count", "tlc", "total leucocyte count"),
    "Platelet Count": ("platelet count", "platelets", "plt", "thrombocyte count"),
    "Neutrophils": ("neutrophils", "neutrophil", "polymorphs", "segmented neutrophils"),
    "Lymphocytes": ("lymphocytes", "lymphocyte", "lymph"),
    "Monocytes": ("monocytes", "monocyte", "mono"),
    "Eosinophils": ("eosinophils", "eosinophil", "eos"),
    "Basophils": ("basophils", "basophil", "baso"),
    "Mean Corpuscular Volume": ("mcv", "mean corpuscular volume"),
    "Mean Corpuscular Haemoglobin": ("mch", "mean corpuscular hemoglobin", "mean corpuscular haemoglobin"),
    "Mean Corpuscular Haemoglobin Concentration": ("mchc", "mean corpuscular hemoglobin concentration"),
    # ── Endocrine ──
    "Thyroxine": ("t4", "thyroxine", "total t4", "tt4"),
    "Free Thyroxine": ("free t4", "ft4", "free thyroxine"),
    "Thyroid Stimulating Hormone": ("tsh", "thyroid stimulating hormone"),
    "Cortisol": ("cortisol", "s. cortisol"),
}


def _normalize_key(text: str) -> str:
    """Strips the punctuation and spacing that varies between labs so 'Alk. Phos'
    and 'alk phos' land on the same lookup key."""
    cleaned = "".join(c if (c.isalnum() or c in "/") else " " for c in text.lower())
    return " ".join(cleaned.split())


@lru_cache(maxsize=1)
def _lookup() -> dict[str, str]:
    table: dict[str, str] = {}
    for canonical, aliases in ANALYTE_ALIASES.items():
        table[_normalize_key(canonical)] = canonical
        for alias in aliases:
            table[_normalize_key(alias)] = canonical
    return table


def canonical_analyte(name: str) -> str | None:
    """Canonical name for an analyte label, or None if it isn't one we know."""
    if not name or not name.strip():
        return None
    return _lookup().get(_normalize_key(name))


def annotate_parameters(parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds `canonical_name` to each parameter that maps to a known analyte, leaving
    the lab's own wording in `name` untouched so nothing is lost in translation."""
    for parameter in parameters:
        canonical = canonical_analyte(parameter.get("name", ""))
        if canonical:
            parameter["canonical_name"] = canonical
    return parameters
