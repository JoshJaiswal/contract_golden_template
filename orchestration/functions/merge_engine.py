"""
merge_engine.py
───────────────
Merges multiple canonical candidate dicts (from different analyzers
or modality sources) into a single final contract package.

Applies precedence rules from precedence-rules.yaml to resolve
field-level conflicts when multiple sources provide different values.

Expected precedence-rules.yaml format:
    source_priority:
      - signed_document      # highest trust
      - final_draft
      - cu_analyzer          # your CU extractions
      - llm_email
      - llm_audio
      - notes                # lowest trust

    field_overrides:         # optional per-field rules
      parties.client.name:
        prefer: cu_analyzer  # always trust CU for this field
      commercials.totalValue:
        prefer: signed_document
"""

import yaml
import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from orchestration.functions.map_to_canonical import build_empty_canonical, get_nested, set_nested

log = logging.getLogger(__name__)

PRECEDENCE_RULES_PATH = Path(__file__).parent.parent.parent / "canonical" / "precedence-rules.yaml"

# Maps _source values to their tier names in precedence-rules.yaml
SOURCE_TO_TIER = {
    "deal_intake":    "cu_analyzer",
    "nda":            "cu_analyzer",
    "sow":            "cu_analyzer",
    "llm_email":      "llm_email",
    "llm_audio":      "llm_audio",
    "signed_document": "signed_document",
    "final_draft":    "final_draft",
}


def load_precedence_rules() -> dict:
    """Load precedence-rules.yaml."""
    # TODO: Add caching
    with open(PRECEDENCE_RULES_PATH, "r") as f:
        return yaml.safe_load(f)


def get_source_priority(rules: dict) -> list[str]:
    """Return ordered list of source tiers, highest priority first."""
    return rules.get("source_priority", [
        "signed_document",
        "final_draft",
        "cu_analyzer",
        "llm_email",
        "llm_audio",
        "notes",
    ])


def get_tier(source: str) -> str:
    """Map a raw _source string to its precedence tier."""
    return SOURCE_TO_TIER.get(source, source)

# Keys that are structural — never treat as missing data fields
STRUCTURAL_KEYS = {
    "missingFields", "conflicts", "provenance", "risks"
}

def collect_all_dot_paths(d: dict, prefix: str = "") -> list[str]:
    """
    Walk a nested dict and return all dot-notation leaf paths.
    Skips internal metadata keys and structural keys.
    """
    paths = []
    for key, val in d.items():
        if key.startswith("_") or key in STRUCTURAL_KEYS:
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            paths.extend(collect_all_dot_paths(val, full_key))
        else:
            paths.append(full_key)
    return paths

def merge_results(candidates: list[dict]) -> dict:
    """
    Merge a list of canonical candidate dicts into one final package.

    For each field in the canonical schema:
    1. Collect all non-empty values across candidates
    2. If only one value exists → use it, record provenance
    3. If multiple agree → use it, record provenance
    4. If multiple conflict → apply precedence rules, record conflict

    Args:
        candidates: List of mapped canonical dicts, each with a "_source" key.

    Returns:
        A single merged canonical package with conflicts and provenance recorded.
    """
    rules = load_precedence_rules()
    priority_order = get_source_priority(rules)
    field_overrides = rules.get("field_overrides", {})

    merged = build_empty_canonical()

    # Gather all field paths from the canonical schema
    all_paths = collect_all_dot_paths(merged)

    for path in all_paths:
        # Collect (value, source, confidence, rule_precedence) from each candidate that has this field
        contributions = []
        for candidate in candidates:
            val = get_nested(candidate, path)
            if val is not None and val != "" and val != []:
                rule_prec = candidate.get("_rule_precedence", {}).get(path, 0)
                contributions.append({
                    "value": val,
                    "source": candidate.get("_source", "unknown"),
                    "confidence": candidate.get("_confidence", 0.0),
                    "rule_precedence": rule_prec,
                })

        if not contributions:
            # No source has this field — add to missingFields
            if path not in merged["missingFields"]:
                merged["missingFields"].append(path)
            continue

        if len(contributions) == 1:
            # Only one source — use it directly
            set_nested(merged, path, contributions[0]["value"])
            _record_provenance(merged, path, contributions[0])
            continue

        # Multiple sources — check if they agree
        unique_values = {str(c["value"]) for c in contributions}
        if len(unique_values) == 1:
            # All agree — use the highest-confidence source
            best = _pick_by_priority(contributions, priority_order, field_overrides, path)
            set_nested(merged, path, best["value"])
            _record_provenance(merged, path, best)
            continue

        # Conflict — apply precedence rules
        best = _pick_by_priority(contributions, priority_order, field_overrides, path)
        set_nested(merged, path, best["value"])
        _record_provenance(merged, path, best)

        # Record the conflict for review
        conflict = {
            "field": path,
            "chosen": best["value"],
            "chosenSource": best["source"],
            "alternatives": [
                {"value": c["value"], "source": c["source"]}
                for c in contributions
                if c["source"] != best["source"]
            ],
        }
        merged["conflicts"].append(conflict)
        log.info(f"[Merge] Conflict on '{path}' — chose {best['source']!r} over {[c['source'] for c in contributions if c['source'] != best['source']]}")

    # Set review status based on what was found
    _set_review_status(merged)

    return merged


def _pick_by_priority(
    contributions: list[dict],
    priority_order: list[str],
    field_overrides: dict,
    path: str,
) -> dict:
    """
    Pick the best contribution for a field based on precedence rules.
    Respects field-level overrides if defined.
    Uses rule-level precedence as tie-breaker when multiple sources 
    are from the same tier.
    """
    # Check for a field-specific override
    if path in field_overrides:
        override_rule = field_overrides[path]
        
        # Check for source-level preference (prefer_source or prefer)
        preferred_source = override_rule.get("prefer_source") or override_rule.get("prefer")
        if preferred_source:
            # First, check if prefer matches a source name directly
            for c in contributions:
                if c["source"] == preferred_source:
                    return c
            # If not found as source, try as tier name
            for c in contributions:
                if get_tier(c["source"]) == preferred_source:
                    return c

    # Fall back to global priority order, using rule precedence as tie-breaker
    for tier in priority_order:
        tier_contributions = [c for c in contributions if get_tier(c["source"]) == tier]
        if tier_contributions:
            if len(tier_contributions) == 1:
                return tier_contributions[0]
            # Multiple sources in same tier — use rule precedence (higher wins)
            best = max(tier_contributions, key=lambda c: c.get("rule_precedence", 0))
            return best

    # Last resort: highest confidence
    return max(contributions, key=lambda c: c["confidence"])


def _record_provenance(merged: dict, path: str, contribution: dict) -> None:
    """Append a provenance entry for a resolved field."""
    entry = {
        "canonicalPath": path,
        "value": str(contribution["value"]) if not isinstance(contribution["value"], list) else "; ".join(str(i) for i in contribution["value"])[:120],
        "sourceDocumentId": "",  # TODO: populate from blob storage URL
        "sourceField": contribution["source"],
        "sourceFamily": get_tier(contribution["source"]),
        "confidence": contribution["confidence"],
    }
    merged["provenance"].append(entry)


def _set_review_status(merged: dict) -> None:
    """
    Set the review.status and reviewReason based on pipeline results.
    - "auto"         → clean extraction, no conflicts, no missing fields
    - "needs_review" → conflicts found or critical fields missing
    - "approved"     → set manually downstream
    """
    reasons = []

    if merged["conflicts"]:
        reasons.append(f"{len(merged['conflicts'])} field conflict(s) found")

    critical_fields = [
        "parties.client.name",
        "parties.vendor.name",
        "dates.effectiveDate",
    ]
    missing_critical = [f for f in critical_fields if f in merged["missingFields"]]
    if missing_critical:
        reasons.append(f"Critical fields missing: {missing_critical}")

    if reasons:
        merged["review"]["status"] = "needs_review"
        merged["review"]["reviewReason"] = reasons
    else:
        merged["review"]["status"] = "auto"

    # Remove review.* from missingFields — set programmatically not extracted
    merged["missingFields"] = [
        f for f in merged["missingFields"]
        if not f.startswith("review.")
    ]