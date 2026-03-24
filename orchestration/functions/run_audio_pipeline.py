# orchestration/functions/run_audio_pipeline.py
import json
import logging
from pathlib import Path

from normalization.audio_handler import handle_audio
from orchestration.functions.map_to_canonical import apply_mapping
from orchestration.functions.merge_engine import merge_results
from validators.schema_validator import validate_canonical_package  # keep if you have this helper

logging.basicConfig(level=logging.INFO)
OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True)

def run_audio_pipeline(input_audio: str, contract_type: str = "auto") -> dict:
    # 0) Get raw facts from audio (you already have this working)
    audio_facts = handle_audio(input_audio, contract_type=contract_type, upload_to_blob=True)
    #    audio_facts is a list[dict]; each dict has _source="llm_audio"

    # 1) STEP 6 — Map: translate raw fields to canonical candidates
    facts_by_source = {"llm_audio": audio_facts}
    candidates = apply_mapping(facts_by_source)

    # 2) STEP 7 — Merge: combine candidates into one canonical package
    merged = merge_results(candidates)

    # 3) Validate against your canonical schema (raises if mismatch)
    # If your validator needs an explicit schema path, pass it here.
    is_valid, errors = validate_canonical_package(merged)
    if not is_valid:
        raise ValueError(
            "[Schema] Canonical package failed validation:\n- " + "\n- ".join(errors[:20])
        )

    # 4) Persist
    out_path = OUT_DIR / "contract_package.from_audio.json"
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"[Pipeline] Wrote {out_path}")
    return merged

if __name__ == "__main__":
    run_audio_pipeline("meeting_sow.m4a", contract_type="nda")