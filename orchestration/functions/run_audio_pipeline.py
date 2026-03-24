# orchestration/functions/run_audio_pipeline.py
import json
import logging
from pathlib import Path
from generation.generate_contract_pdf import generate_pdf

from normalization.audio_handler import handle_audio
from orchestration.functions.map_to_canonical import apply_mapping
from orchestration.functions.merge_engine import merge_results
from validators.schema_validator import validate_canonical_package  # keep if you have this helper

logging.basicConfig(level=logging.INFO)
OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

# In orchestration/functions/run_audio_pipeline.py (top or just above run_audio_pipeline)

def infer_doc_type(canonical: dict, hint: str | None = None) -> str:
    """
    Decide 'nda' vs 'sow' from the canonical package, with optional hint override.
    Priority:
      1) explicit hint arg (if 'nda' or 'sow')
      2) parties.ndaType (values like 'NDA', 'SOW', 'unknown')
      3) heuristic based on scope/commercials richness
      4) fallback to 'nda'
    """
    # 1) explicit hint
    if hint and hint.lower() in {"nda", "sow"}:
        return hint.lower()

    # 2) explicit field
    nda_type = (canonical.get("parties", {})
                         .get("ndaType", "") or "").strip().lower()
    if nda_type == "nda":
        return "nda"
    if nda_type == "sow":
        return "sow"

    # 3) heuristic: if it looks like a SOW (deliverables/milestones/commercial terms present)
    scope = canonical.get("scope", {})
    comm  = canonical.get("commercials", {})
    if any(scope.get(k) for k in ("deliverables", "milestones", "description")) \
       or any(comm.get(k) for k in ("pricingModel", "totalValue", "paymentTerms")):
        return "sow"

    # 4) fallback
    return "nda"

def _slug(s: str) -> str:
    # safe file name helper
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (s or ""))[:80]

def run_audio_pipeline(
    input_audio: str,
    contract_type: str = "auto",
    render: str = "auto"  # "auto" | "nda" | "sow" | "both"
) -> dict:

    # 0) Get raw facts from audio
    audio_facts = handle_audio(input_audio, contract_type=contract_type, upload_to_blob=True)
    # audio_facts is a list[dict]; each dict has _source="llm_audio"

    # 1) STEP 6 — Map
    facts_by_source = {"llm_audio": audio_facts}
    candidates = apply_mapping(facts_by_source)

    # 2) STEP 7 — Merge
    merged = merge_results(candidates)

    # 3) Validate against canonical schema
    is_valid, errors = validate_canonical_package(merged)
    if not is_valid:
        raise ValueError("[Schema] Canonical package failed validation:\n- " + "\n- ".join(errors[:20]))

    # 4) Persist canonical JSON
    out_json = OUT_DIR / "contract_package.from_audio.json"
    out_json.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"[Pipeline] Wrote {out_json}")

    # ─────────────────────────────────────────────────────────────────────
    # 5) Generate PDF(s) — THIS IS THE NEW BLOCK YOU ASKED ABOUT
    # ─────────────────────────────────────────────────────────────────────

    # Decide which doc types to render
    render = (render or "auto").lower()
    if render not in {"auto", "nda", "sow", "both"}:
        logging.warning(f"[Pipeline] Unknown render='{render}', defaulting to 'auto'")
        render = "auto"

    if render == "auto":
        # infer NDA vs SOW from canonical (uses parties.ndaType and simple heuristics)
        doc_types = [infer_doc_type(merged)]
    elif render == "both":
        doc_types = ["nda", "sow"]
    else:
        doc_types = [render]  # "nda" or "sow"

    # Build nice, deterministic filenames
    client = merged.get("parties", {}).get("client", {}).get("name", "CLIENT")
    vendor = merged.get("parties", {}).get("vendor", {}).get("name", "VENDOR")
    base = f"{_slug(client)}_x_{_slug(vendor)}"

    for dt in doc_types:
        pdf_name = f"{dt.upper()}_{base}.pdf"
        pdf_path = OUT_DIR / pdf_name
        generate_pdf(merged, dt, str(pdf_path))
        logging.info(f"[Pipeline] PDF written ⇒ {pdf_path}")

    return merged

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="One-shot E2E: audio → canonical → merge → validate → PDF")
    parser.add_argument("--input", default="meeting_sow.m4a", help="Path to audio file (.mp3/.wav/.m4a)")
    parser.add_argument("--type", default="auto", choices=["auto", "nda", "sow"], help="Pipeline hint for extraction")
    parser.add_argument("--render", default="auto", choices=["auto", "nda", "sow", "both"],
                        help="Which PDF(s) to generate from the canonical package")
    args = parser.parse_args()

    # contract_type is a hint for extraction (not the output doc type)
    run_audio_pipeline(args.input, contract_type=args.type, render=args.render)