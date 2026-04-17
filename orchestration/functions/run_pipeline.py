"""
run_pipeline.py
───────────────
ENTRY POINT for the full contract processing pipeline.

Accepts any supported input file, routes it to the correct
modality handler, runs the appropriate CU analyzer(s) or
LLM extractor, maps to canonical schema, merges conflicts,
and returns a validated contract package.

After merging, the canonical package is written to the
Cosmos DB knowledge graph via graph_builder.

Usage:
    python run_pipeline.py --input path/to/file.pdf --type nda
    python run_pipeline.py --input path/to/email.eml
    python run_pipeline.py --input path/to/call.mp3
"""

import argparse
import json
import logging
from dotenv import load_dotenv
load_dotenv()
import sys
from pathlib import Path
from typing import Literal, Optional

# Ensure package imports work when executing script directly from project root.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from orchestration.functions.map_to_canonical import map_to_canonical
from orchestration.functions.merge_engine import merge_results
from generation.generate_contract_pdf import generate_pdf
from normalization.pdf_handler import handle_pdf
from normalization.docx_handler import handle_docx
from normalization.email_handler import handle_email
from normalization.audio_handler import handle_audio
from validators.schema_validator import validate_canonical_package

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Supported input types and their handlers
MODALITY_ROUTER = {
    ".pdf":  handle_pdf,
    ".docx": handle_docx,
    ".doc":  handle_docx,
    ".eml":  handle_email,
    ".msg":  handle_email,
    ".mp3":  handle_audio,
    ".wav":  handle_audio,
    ".m4a":  handle_audio,
}

ContractType = Literal["nda", "sow", "auto", "both"]


def run_pipeline(
    input_path:     str,
    contract_type:  ContractType = "auto",
    job_id:         Optional[str] = None,
    upload_to_blob: bool = True,
) -> dict:
    """
    Main pipeline entry point.

    Args:
        input_path:     Local path to the input file.
        contract_type:  "nda" | "sow" | "auto" | "both"
        job_id:         Optional job ID for graph building. If None, graph step is skipped.
        upload_to_blob: Whether to stage file in Azure Blob before processing.

    Returns:
        A validated canonical contract package (dict matching schema).
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {input_path}. "
            "Verify the path and try again."
        )

    ext = path.suffix.lower()
    if ext not in MODALITY_ROUTER:
        raise ValueError(f"Unsupported file type: {ext}. Supported: {list(MODALITY_ROUTER)}")

    log.info(f"[Pipeline] Starting — file={path.name}, type={contract_type}, job_id={job_id}")

    # ── Step 1: Route to modality handler ────────────────────────────────────
    handler = MODALITY_ROUTER[ext]
    raw_results: list[dict] = handler(
        file_path=str(path),
        contract_type=contract_type,
        upload_to_blob=upload_to_blob,
    )
    log.info(f"[Pipeline] Extraction complete — {len(raw_results)} result(s) from handler")

    # ── Step 2: Map each result to canonical schema fields ───────────────────
    canonical_candidates: list[dict] = []
    for result in raw_results:
        mapped = map_to_canonical(result)
        canonical_candidates.append(mapped)

    # ── Step 3: Merge + apply precedence rules ────────────────────────────────
    merged_package = merge_results(canonical_candidates)
    log.info("[Pipeline] Merge complete")

    # ── Step 4: Validate against canonical schema ─────────────────────────────
    is_valid, errors = validate_canonical_package(merged_package)
    if not is_valid:
        log.warning(f"[Pipeline] Schema validation warnings: {errors}")
        merged_package["_validationErrors"] = errors
    else:
        log.info("[Pipeline] Schema validation passed")

    # ── Step 5: Build knowledge graph ─────────────────────────────────────────
    # Only runs when a job_id is supplied (i.e. called from the API, not CLI).
    # Graph build failures are logged but do NOT block the pipeline response.
    if job_id:
        try:
            from orchestration.functions.graph_builder import build_graph_from_canonical
            build_graph_from_canonical(job_id=job_id, canonical=merged_package)
            log.info(f"[Pipeline] Knowledge graph built for job {job_id}")
        except Exception as graph_err:
            log.warning(
                f"[Pipeline] Knowledge graph build failed for job {job_id} — "
                f"continuing without graph. Error: {graph_err}"
            )

    return merged_package


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Contract Processing Pipeline")
    parser.add_argument("--input",    required=True, help="Path to input file")
    parser.add_argument("--type",     default="auto", choices=["nda", "sow", "auto", "both"])
    parser.add_argument("--no-blob",  action="store_true", help="Skip Blob Storage upload")
    parser.add_argument("--output",   help="Save canonical JSON to this file path")
    parser.add_argument("--generate", action="store_true",
                        help="Generate single PDF contract after extraction")
    parser.add_argument("--output-pdf", help="Path for generated PDF (requires --generate)")
    parser.add_argument("--generate-both", action="store_true",
                        help="Generate both NDA and SOW PDFs after extraction")
    parser.add_argument("--output-dir", default="tests/output",
                        help="Output directory for --generate-both (default: tests/output)")
    args = parser.parse_args()

    result = run_pipeline(
        input_path=args.input,
        contract_type=args.type,
        upload_to_blob=not args.no_blob,
        # job_id is None when running from CLI — graph step is skipped
    )

    # Save canonical JSON
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        log.info(f"[Pipeline] Canonical JSON saved to {args.output}")
    else:
        print(json.dumps(result, indent=2))

    # Generate single PDF
    if args.generate:
        contract_type = args.type if args.type != "auto" else "nda"
        pdf_path = args.output_pdf or (
            args.output.replace(".json", f"-{contract_type}.pdf")
            if args.output else f"tests/output/generated-{contract_type}.pdf"
        )
        generate_pdf(result, contract_type, pdf_path)
        log.info(f"[Pipeline] PDF generated: {pdf_path}")

    # Generate both NDA and SOW PDFs
    if args.generate_both:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        base     = Path(args.input).stem
        nda_path = str(out_dir / f"{base}-nda.pdf")
        sow_path = str(out_dir / f"{base}-sow.pdf")

        generate_pdf(result, "nda", nda_path)
        log.info(f"[Pipeline] NDA PDF generated: {nda_path}")

        generate_pdf(result, "sow", sow_path)
        log.info(f"[Pipeline] SOW PDF generated: {sow_path}")

        log.info(f"[Pipeline] Both documents saved to {out_dir}/")