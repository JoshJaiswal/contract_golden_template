"""
job_store.py
─────────────
Cosmos DB-backed job persistence layer.
Replaces the in-memory JOBS dict in api.py.

All reads and writes go through this module so api.py
stays clean and the storage backend can be swapped easily.

Document structure (mirrors the old in-memory dict exactly):
    {
        "id":            "<job_id>",        # Cosmos DB requires "id"
        "job_id":        "<job_id>",
        "status":        "queued | processing | complete | failed",
        "created_at":    "<iso-datetime>",
        "completed_at":  "<iso-datetime>",
        "file_name":     "<original filename>",
        "contract_type": "nda | sow | auto | both",
        "outputs":       { "canonical": "...", "nda_pdf": "...", ... } | None,
        "error":         "<message>" | None,
    }
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from config.cosmos_client import get_jobs_container

log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ─────────────────────────────────────────────────────────────────

def create_job(job_id: str, file_name: str, contract_type: str) -> dict:
    """
    Create and persist a new job document in Cosmos DB.
    Returns the job dict.
    """
    job = {
        "id":            job_id,   # Cosmos DB primary key
        "job_id":        job_id,
        "status":        "queued",
        "created_at":    _now(),
        "completed_at":  None,
        "file_name":     file_name,
        "contract_type": contract_type,
        "outputs":       None,
        "error":         None,
    }
    container = get_jobs_container()
    container.create_item(body=job)
    log.info(f"[JobStore] Created job {job_id}")
    return job


def get_job(job_id: str) -> Optional[dict]:
    """
    Fetch a job by ID. Returns None if not found.
    """
    try:
        container = get_jobs_container()
        return container.read_item(item=job_id, partition_key=job_id)
    except CosmosResourceNotFoundError:
        return None
    except Exception as e:
        log.error(f"[JobStore] get_job({job_id}) failed: {e}")
        raise


def update_job(job_id: str, updates: dict) -> dict:
    """
    Patch a job document with the provided key/value updates.
    Automatically stamps updated_at.
    Returns the updated job dict.
    """
    job = get_job(job_id)
    if job is None:
        raise KeyError(f"Job {job_id} not found in Cosmos DB")

    job.update(updates)
    job["updated_at"] = _now()

    container = get_jobs_container()
    container.replace_item(item=job_id, body=job)
    log.debug(f"[JobStore] Updated job {job_id}: {list(updates.keys())}")
    return job


def delete_job(job_id: str) -> None:
    """
    Delete a job document from Cosmos DB.
    """
    try:
        container = get_jobs_container()
        container.delete_item(item=job_id, partition_key=job_id)
        log.info(f"[JobStore] Deleted job {job_id}")
    except CosmosResourceNotFoundError:
        log.warning(f"[JobStore] delete_job({job_id}) — document not found, skipping")
    except Exception as e:
        log.error(f"[JobStore] delete_job({job_id}) failed: {e}")
        raise


def list_jobs(limit: int = 50) -> list[dict]:
    """
    Return up to `limit` jobs ordered by creation time (newest first).
    """
    container = get_jobs_container()
    query = (
        "SELECT c.job_id, c.status, c.file_name, c.contract_type, c.created_at "
        "FROM c ORDER BY c.created_at DESC OFFSET 0 LIMIT @limit"
    )
    items = list(container.query_items(
        query=query,
        parameters=[{"name": "@limit", "value": limit}],
        enable_cross_partition_query=True,
    ))
    return items


def job_exists(job_id: str) -> bool:
    """Quick existence check without raising."""
    return get_job(job_id) is not None