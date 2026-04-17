"""
api.py
──────
FastAPI endpoint for the Contract Intelligence Pipeline.

Accepts file uploads, runs the full pipeline asynchronously,
and returns generated NDA and SOW PDFs for download.

Usage (local):
    pip install fastapi uvicorn python-multipart
    python api.py

Then open: http://localhost:8000/docs  (interactive API docs)

Endpoints:
    POST /analyze                   — upload file, get job_id back
    GET  /jobs/{job_id}             — check status, get download URLs when ready
    GET  /jobs                      — list all jobs
    DELETE /jobs/{job_id}           — delete a job and its files
    POST /jobs/{job_id}/regenerate  — re-run PDF generation with overrides
    GET  /download/{job_id}/nda     — download NDA PDF
    GET  /download/{job_id}/sow     — download SOW PDF
    GET  /download/{job_id}/canonical — download canonical JSON
    GET  /download/{job_id}/source  — download original uploaded file
    GET  /graph/{job_id}/parties    — graph: parties linked to a contract
    GET  /graph/{job_id}/obligations — graph: obligations linked to a contract
    GET  /graph/{job_id}/deliverables — graph: deliverables linked to a contract
    GET  /graph/party/{party_name}  — graph: all contracts involving a party
    GET  /graph/{job_id}/full       — graph: all vertices + edges for a contract
    POST /graph/query               — graph: run a raw Gremlin query (power users)
    GET  /health                    — health check
"""

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Security, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("contract-api")

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Contract Intelligence Platform",
    description=(
        "Transforms unstructured contract documents into standardised "
        "NDA and SOW PDFs using Azure Content Understanding, "
        "with Cosmos DB job persistence and a knowledge graph."
    ),
    version="2.0.0",
)

def get_api_key_for_limit(request: Request):
    return request.headers.get("X-API-Key") or request.client.host

limiter = Limiter(key_func=get_api_key_for_limit)
app.state.limiter = limiter

# Allow all origins locally — lock this down before production deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
    )

# ── API Key auth ──────────────────────────────────────────────────────────────
API_KEY        = os.getenv("CONTRACT_API_KEY", "GoldenEY1479")
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# ── Directories ───────────────────────────────────────────────────────────────
UPLOAD_DIR = Path("api_uploads")
OUTPUT_DIR = Path("api_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Supported file types
SUPPORTED_TYPES = {
    "application/pdf":                          ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword":                       ".doc",
    "message/rfc822":                           ".eml",
    "audio/mpeg":                               ".mp3",
    "audio/wav":                                ".wav",
    "audio/x-wav":                              ".wav",
    "audio/mp4":                                ".m4a",
}


# ── Background pipeline runner ────────────────────────────────────────────────
async def run_pipeline_job(job_id: str, file_path: str, contract_type: str):
    """
    Run the full pipeline in the background.
    Updates the Cosmos DB job document with status and output paths.
    """
    import asyncio
    from orchestration.functions.job_store import update_job

    update_job(job_id, {"status": "processing"})
    log.info(f"[Job {job_id}] Pipeline starting — file={Path(file_path).name}")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _run_pipeline_sync,
            job_id,
            file_path,
            contract_type,
        )
        update_job(job_id, {
            "status":       "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "outputs":      result,
        })
        log.info(f"[Job {job_id}] Complete")

    except Exception as e:
        log.error(f"[Job {job_id}] Failed: {e}", exc_info=True)
        update_job(job_id, {
            "status":       "failed",
            "error":        str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


def _run_pipeline_sync(job_id: str, file_path: str, contract_type: str) -> dict:
    """
    Synchronous pipeline execution (runs in thread pool).
    Returns dict of output file paths.
    """
    import sys, json
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from orchestration.functions.run_pipeline import run_pipeline
    from generation.generate_contract_pdf import generate_pdf

    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(exist_ok=True)

    # Step 1 — Run extraction pipeline (also builds the knowledge graph internally)
    canonical = run_pipeline(
        input_path=file_path,
        contract_type=contract_type,
        job_id=job_id,
        upload_to_blob=True,
    )

    # Step 2 — Save canonical JSON
    canonical_path = job_output_dir / "canonical.json"
    with open(canonical_path, "w") as f:
        json.dump(canonical, f, indent=2)

    # Step 3 — Decide which docs to generate
    outputs = {"canonical": str(canonical_path)}

    if contract_type == "both":
        generate_nda = True
        generate_sow = True

    elif contract_type == "nda":
        generate_nda = True
        generate_sow = False

    elif contract_type == "sow":
        generate_nda = False
        generate_sow = True

    else:  # "auto"
        parties         = canonical.get("parties", {})
        scope           = canonical.get("scope", {})
        commercials     = canonical.get("commercials", {})
        confidentiality = canonical.get("confidentiality", {})

        nda_type = str(parties.get("ndaType", "")).lower()
        has_nda_signal = (
            "nda" in nda_type
            or bool(confidentiality.get("term"))
            or bool(confidentiality.get("exceptions"))
            or bool(parties.get("disclosingParty"))
        )
        has_sow_signal = (
            bool(scope.get("deliverables"))
            or bool(scope.get("outOfScope"))
            or bool(commercials.get("totalValue"))
            or bool(commercials.get("milestones"))
            or bool(commercials.get("paymentTerms"))
        )

        generate_nda = has_nda_signal
        generate_sow = has_sow_signal

        if not generate_nda and not generate_sow:
            log.warning(f"[Job {job_id}] Auto-detect: no strong signals found — generating both as fallback")
            generate_nda = True
            generate_sow = True
        else:
            log.info(f"[Job {job_id}] Auto-detect: nda={generate_nda}, sow={generate_sow}")

    # Step 4 — Generate only the decided doc(s)
    if generate_nda:
        nda_path = str(job_output_dir / "generated-nda.pdf")
        generate_pdf(canonical, "nda", nda_path)
        outputs["nda_pdf"] = nda_path
        log.info(f"[Job {job_id}] NDA PDF generated")

    if generate_sow:
        sow_path = str(job_output_dir / "generated-sow.pdf")
        generate_pdf(canonical, "sow", sow_path)
        outputs["sow_pdf"] = sow_path
        log.info(f"[Job {job_id}] SOW PDF generated")

    return outputs


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    """Check API is running."""
    return {
        "status":  "ok",
        "version": "2.0.0",
        "time":    datetime.now(timezone.utc).isoformat(),
    }


@limiter.limit("5/minute")
@app.post("/analyze", tags=["Pipeline"])
async def analyze(
    request:       Request,
    file:          UploadFile = File(..., description="Contract document to process"),
    contract_type: str        = Form("auto", description="nda | sow | auto | both"),
    _key:          str        = Security(verify_api_key),
):
    """
    Upload a contract document and start the extraction pipeline.

    Returns a job_id. Poll GET /jobs/{job_id} to check status.
    When status = 'complete', download URLs will be included.

    Supported formats: PDF, DOCX, EML, MP3, WAV, M4A
    """
    from orchestration.functions.job_store import create_job

    # Validate file type
    file_ext = Path(file.filename or "").suffix.lower()
    allowed_extensions = {".pdf", ".docx", ".doc", ".eml", ".mp3", ".wav", ".m4a"}
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file_ext}. Allowed: {sorted(allowed_extensions)}"
        )

    # Validate contract_type
    if contract_type not in ("nda", "sow", "auto", "both"):
        raise HTTPException(
            status_code=422,
            detail="contract_type must be 'nda', 'sow', 'both', or 'auto'"
        )

    # Save uploaded file
    job_id    = str(uuid.uuid4())
    safe_name = f"{job_id}{file_ext}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    log.info(
        f"[Job {job_id}] File received — "
        f"name={file.filename}, size={file_path.stat().st_size} bytes"
    )

    # Persist job to Cosmos DB
    create_job(
        job_id=job_id,
        file_name=file.filename,
        contract_type=contract_type,
    )

    # Start pipeline in background
    import asyncio
    asyncio.create_task(
        run_pipeline_job(job_id, str(file_path), contract_type)
    )

    return {
        "job_id":   job_id,
        "status":   "queued",
        "message":  "Pipeline started. Poll /jobs/{job_id} for status.",
        "poll_url": f"/jobs/{job_id}",
    }


@app.get("/jobs/{job_id}", tags=["Pipeline"])
def get_job(
    job_id: str,
    _key:   str = Security(verify_api_key),
):
    """
    Get the status and results of a pipeline job.

    Status values:
    - queued      — waiting to start
    - processing  — pipeline running
    - complete    — finished, download URLs available
    - failed      — error occurred, see 'error' field
    """
    from orchestration.functions.job_store import get_job as _get_job

    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = dict(job)  # make a copy — don't mutate the Cosmos document

    # Add download URLs if complete
    if job["status"] == "complete":
        base    = f"/download/{job_id}"
        outputs = job.get("outputs") or {}
        job["download_urls"] = {
            k: f"{base}/{k.replace('_pdf', '')}"
            for k in outputs
            if k.endswith("_pdf")
        }

    return job


@app.get("/jobs", tags=["System"])
def list_jobs(_key: str = Security(verify_api_key)):
    """List the 50 most recent jobs and their current status."""
    from orchestration.functions.job_store import list_jobs as _list_jobs

    jobs = _list_jobs(limit=50)
    return {
        "total": len(jobs),
        "jobs":  jobs,
    }


@app.delete("/jobs/{job_id}", tags=["System"])
def delete_job(
    job_id: str,
    _key:   str = Security(verify_api_key),
):
    """Delete a job and its associated files from disk and Cosmos DB."""
    from orchestration.functions.job_store import get_job as _get_job, delete_job as _delete_job

    if not _get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Clean up output files
    job_output_dir = OUTPUT_DIR / job_id
    if job_output_dir.exists():
        shutil.rmtree(job_output_dir)

    # Clean up uploaded file
    upload_file = next(UPLOAD_DIR.glob(f"{job_id}.*"), None)
    if upload_file:
        upload_file.unlink(missing_ok=True)

    # Delete from Cosmos DB
    _delete_job(job_id)

    return {"message": f"Job {job_id} deleted"}


# ── Downloads ─────────────────────────────────────────────────────────────────

@app.get("/download/{job_id}/nda", tags=["Downloads"])
def download_nda(
    job_id: str,
    _key:   str = Security(verify_api_key),
):
    """Download the generated NDA PDF for a completed job."""
    _validate_download(job_id)
    pdf_path = OUTPUT_DIR / job_id / "generated-nda.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="NDA PDF not found")

    filename = _safe_filename(job_id, "nda")
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=filename)


@app.get("/download/{job_id}/sow", tags=["Downloads"])
def download_sow(
    job_id: str,
    _key:   str = Security(verify_api_key),
):
    """Download the generated SOW PDF for a completed job."""
    _validate_download(job_id)
    pdf_path = OUTPUT_DIR / job_id / "generated-sow.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="SOW PDF not found")

    filename = _safe_filename(job_id, "sow")
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=filename)


@app.get("/download/{job_id}/canonical", tags=["Downloads"])
def download_canonical(job_id: str, _key: str = Security(verify_api_key)):
    """Download the canonical JSON for a completed job."""
    canonical_path = OUTPUT_DIR / job_id / "canonical.json"
    if not canonical_path.exists():
        raise HTTPException(status_code=404, detail="Canonical JSON not found")
    return FileResponse(
        canonical_path,
        media_type="application/json",
        filename=f"{job_id}-canonical.json",
    )


@app.get("/download/{job_id}/source", tags=["Downloads"])
def download_source(job_id: str, _key: str = Security(verify_api_key)):
    """Return the original uploaded file so the frontend can preview it."""
    from orchestration.functions.job_store import get_job as _get_job

    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    matches = list(UPLOAD_DIR.glob(f"{job_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Source file not found")

    source_path = matches[0]
    ext = source_path.suffix.lower()

    mime_map = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc":  "application/msword",
        ".eml":  "message/rfc822",
        ".mp3":  "audio/mpeg",
        ".wav":  "audio/wav",
        ".m4a":  "audio/mp4",
        ".txt":  "text/plain",
    }
    media_type   = mime_map.get(ext, "application/octet-stream")
    original_name = job.get("file_name", f"source{ext}")

    return FileResponse(path=str(source_path), media_type=media_type, filename=original_name)


# ── Regenerate ────────────────────────────────────────────────────────────────

class RegenerateRequest(BaseModel):
    overrides: dict
    dismissed_fields: List[str] = []


@app.post("/jobs/{job_id}/regenerate", tags=["Pipeline"])
async def regenerate_job(
    job_id: str,
    body:   RegenerateRequest,
    _key:   str = Security(verify_api_key),
):
    """
    Patch the saved canonical JSON with user-supplied overrides, remove
    dismissed conflicts, and re-run ONLY the PDF generation step.

    No Azure calls are made — extraction is skipped entirely.
    """
    from orchestration.functions.job_store import get_job as _get_job, update_job

    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job["status"] != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Job must be 'complete' to regenerate. Current status: {job['status']}",
        )

    canonical_path = OUTPUT_DIR / job_id / "canonical.json"
    if not canonical_path.exists():
        raise HTTPException(
            status_code=404,
            detail="canonical.json not found — was the original job completed successfully?",
        )

    # Re-queue the same job_id so frontend poll works as-is
    update_job(job_id, {"status": "queued", "error": None})

    import asyncio
    asyncio.create_task(
        _run_regenerate_job(
            job_id,
            str(canonical_path),
            body.overrides,
            body.dismissed_fields,
            job.get("contract_type", "auto"),
        )
    )

    return {
        "job_id":              job_id,
        "status":              "queued",
        "message":             (
            f"Regeneration queued with {len(body.overrides)} override(s) "
            f"and {len(body.dismissed_fields)} dismissed conflict(s). "
            f"Poll /jobs/{job_id}."
        ),
        "poll_url":            f"/jobs/{job_id}",
        "overrides_applied":   list(body.overrides.keys()),
        "conflicts_dismissed": body.dismissed_fields,
    }


async def _run_regenerate_job(
    job_id: str,
    canonical_path: str,
    overrides: dict,
    dismissed_fields: list,
    contract_type: str,
):
    """Background task: patch canonical → remove dismissed conflicts → regenerate PDFs."""
    import asyncio
    from orchestration.functions.job_store import update_job

    update_job(job_id, {"status": "processing"})
    log.info(
        f"[Job {job_id}] Regenerating — "
        f"overrides: {list(overrides.keys())} | dismissed: {dismissed_fields}"
    )
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _regenerate_sync,
            job_id,
            canonical_path,
            overrides,
            dismissed_fields,
            contract_type,
        )
        update_job(job_id, {
            "status":       "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "outputs":      result,
        })
        log.info(f"[Job {job_id}] Regeneration complete")
    except Exception as e:
        log.error(f"[Job {job_id}] Regeneration failed: {e}", exc_info=True)
        update_job(job_id, {
            "status":       "failed",
            "error":        str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


def _set_nested(d: dict, dot_path: str, value):
    """Set a value in a nested dict using dot notation."""
    keys = dot_path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def _regenerate_sync(
    job_id: str,
    canonical_path: str,
    overrides: dict,
    dismissed_fields: list,
    contract_type: str,
) -> dict:
    """
    1. Load saved canonical.json
    2. Remove dismissed conflicts from canonical["conflicts"]
    3. Apply field overrides (dot-notation)
    4. Save updated canonical.
    5. Regenerate PDFs
    """
    import sys, json
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from generation.generate_contract_pdf import generate_pdf

    job_output_dir = OUTPUT_DIR / job_id

    # Step 1: Load canonical
    with open(canonical_path, "r") as f:
        canonical = json.load(f)

    # Step 2: Remove dismissed conflicts
    if dismissed_fields:
        dismissed_set      = set(dismissed_fields)
        original_conflicts = canonical.get("conflicts", [])
        canonical["conflicts"] = [
            c for c in original_conflicts
            if c.get("field", "") not in dismissed_set
        ]
        removed = len(original_conflicts) - len(canonical["conflicts"])
        log.info(f"[Job {job_id}] Removed {removed} dismissed conflict(s) from canonical")

    # Step 3: Apply field overrides
    if overrides:
        overridden_fields = set(overrides.keys())
        canonical["conflicts"] = [
            c for c in canonical.get("conflicts", [])
            if c.get("field", "") not in overridden_fields
        ]
        for dot_path, value in overrides.items():
            try:
                _set_nested(canonical, dot_path, value)
                log.info(f"[Job {job_id}] Override applied: {dot_path} = {str(value)[:60]}")
            except Exception as e:
                log.warning(f"[Job {job_id}] Could not apply override '{dot_path}': {e}")

    # Step 3b: Remove filled fields from missingFields
    if overrides:
        filled_keys = set(overrides.keys())
        for mf_key in ("missingFields", "missing_fields"):
            existing = canonical.get(mf_key)
            if not existing:
                continue
            if isinstance(existing, list):
                cleaned = []
                for entry in existing:
                    if isinstance(entry, str):
                        if not any(
                            entry == k or entry == k.split(".")[-1] or k.endswith("." + entry)
                            for k in filled_keys
                        ):
                            cleaned.append(entry)
                    elif isinstance(entry, dict):
                        field_name = entry.get("field", "")
                        if not any(
                            field_name == k or field_name == k.split(".")[-1] or k.endswith("." + field_name)
                            for k in filled_keys
                        ):
                            cleaned.append(entry)
                    else:
                        cleaned.append(entry)
                removed_mf = len(existing) - len(cleaned)
                if removed_mf:
                    canonical[mf_key] = cleaned
                    log.info(f"[Job {job_id}] Removed {removed_mf} filled field(s) from {mf_key}")

    # Step 4: Save updated canonical
    with open(canonical_path, "w") as f:
        json.dump(canonical, f, indent=2)
    log.info(f"[Job {job_id}] canonical.json updated and saved")

    # Step 5: Regenerate PDFs
    outputs = {"canonical": canonical_path}

    if contract_type == "both":
        generate_nda, generate_sow = True, True
    elif contract_type == "nda":
        generate_nda, generate_sow = True, False
    elif contract_type == "sow":
        generate_nda, generate_sow = False, True
    else:  # auto
        parties         = canonical.get("parties", {})
        scope           = canonical.get("scope", {})
        commercials     = canonical.get("commercials", {})
        confidentiality = canonical.get("confidentiality", {})

        nda_type = str(parties.get("ndaType", "")).lower()
        generate_nda = (
            "nda" in nda_type
            or bool(confidentiality.get("term"))
            or bool(confidentiality.get("exceptions"))
            or bool(parties.get("disclosingParty"))
        )
        generate_sow = (
            bool(scope.get("deliverables"))
            or bool(scope.get("outOfScope"))
            or bool(commercials.get("totalValue"))
            or bool(commercials.get("milestones"))
            or bool(commercials.get("paymentTerms"))
        )
        if not generate_nda and not generate_sow:
            generate_nda = generate_sow = True

    if generate_nda:
        nda_path = str(job_output_dir / "generated-nda.pdf")
        generate_pdf(canonical, "nda", nda_path)
        outputs["nda_pdf"] = nda_path
        log.info(f"[Job {job_id}] NDA PDF regenerated")

    if generate_sow:
        sow_path = str(job_output_dir / "generated-sow.pdf")
        generate_pdf(canonical, "sow", sow_path)
        outputs["sow_pdf"] = sow_path
        log.info(f"[Job {job_id}] SOW PDF regenerated")

    return outputs


# ── Knowledge Graph Endpoints ─────────────────────────────────────────────────

class GremlinQueryRequest(BaseModel):
    query: str


@app.get("/graph/{job_id}/parties", tags=["Knowledge Graph"])
def graph_parties(job_id: str, _key: str = Security(verify_api_key)):
    """Return all Party vertices linked to a contract."""
    from orchestration.functions.graph_builder import get_contract_parties
    try:
        result = get_contract_parties(job_id)
        return {"job_id": job_id, "parties": result}
    except Exception as e:
        log.error(f"[Graph] get_contract_parties({job_id}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/{job_id}/obligations", tags=["Knowledge Graph"])
def graph_obligations(job_id: str, _key: str = Security(verify_api_key)):
    """Return all Obligation vertices linked to a contract."""
    from orchestration.functions.graph_builder import get_contract_obligations
    try:
        result = get_contract_obligations(job_id)
        return {"job_id": job_id, "obligations": result}
    except Exception as e:
        log.error(f"[Graph] get_contract_obligations({job_id}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/{job_id}/deliverables", tags=["Knowledge Graph"])
def graph_deliverables(job_id: str, _key: str = Security(verify_api_key)):
    """Return all Deliverable vertices linked to a contract."""
    from orchestration.functions.graph_builder import get_contract_deliverables
    try:
        result = get_contract_deliverables(job_id)
        return {"job_id": job_id, "deliverables": result}
    except Exception as e:
        log.error(f"[Graph] get_contract_deliverables({job_id}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/party/{party_name}", tags=["Knowledge Graph"])
def graph_contracts_by_party(party_name: str, _key: str = Security(verify_api_key)):
    """Find all contracts that involve a named party (cross-contract query)."""
    from orchestration.functions.graph_builder import get_contracts_by_party
    try:
        result = get_contracts_by_party(party_name)
        return {"party_name": party_name, "contracts": result}
    except Exception as e:
        log.error(f"[Graph] get_contracts_by_party({party_name}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/graph/{job_id}/full", tags=["Knowledge Graph"])
def graph_full(job_id: str, _key: str = Security(verify_api_key)):
    """Return the full graph (vertices + edges) for a contract. Used by the frontend visualiser."""
    from orchestration.functions.graph_builder import get_full_graph
    try:
        result = get_full_graph(job_id)
        return {"job_id": job_id, **result}
    except Exception as e:
        log.error(f"[Graph] get_full_graph({job_id}) failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/query", tags=["Knowledge Graph"])
def graph_raw_query(body: GremlinQueryRequest, _key: str = Security(verify_api_key)):
    """
    Execute a raw Gremlin query against the knowledge graph.
    For power users and debugging. Example:
        { "query": "g.V().hasLabel('Party').valueMap(true)" }
    """
    from config.gremlin_client import run_gremlin_query
    try:
        result = run_gremlin_query(body.query)
        return {"result": result}
    except Exception as e:
        log.error(f"[Graph] raw query failed: {e}\nQuery: {body.query}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_download(job_id: str):
    from orchestration.functions.job_store import get_job as _get_job

    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job["status"] == "processing":
        raise HTTPException(status_code=202, detail="Job still processing")
    if job["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Job failed: {job.get('error', 'unknown error')}"
        )
    if job["status"] != "complete":
        raise HTTPException(status_code=400, detail=f"Job status: {job['status']}")


def _safe_filename(job_id: str, doc_type: str) -> str:
    """Generate a clean download filename from job metadata."""
    from orchestration.functions.job_store import get_job as _get_job

    job      = _get_job(job_id) or {}
    original = Path(job.get("file_name", "contract")).stem
    safe     = "".join(c for c in original if c.isalnum() or c in "-_ ")
    safe     = safe.strip()[:40] or "contract"
    return f"{safe}-{doc_type}.pdf"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
    