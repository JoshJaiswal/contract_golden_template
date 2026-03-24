"""
pdf_handler.py
──────────────
Handles PDF inputs through Azure Content Understanding.
Uses the exact client pattern from Azure's own code example.
API version: 2025-05-01-preview
"""

import logging
import os
import time
import requests
from pathlib import Path
from typing import Literal
from collections.abc import Callable

log = logging.getLogger(__name__)

# ── Your 3 analyzer IDs ───────────────────────────────────────────────────────
CU_ANALYZER_IDS = {
    "deal_intake": "core-deal-intake-analyzer-02",
    "nda":         "nda-analyzer-extractor",
    "sow":         "sow-analyzer-extractor-02",
}

BLOB_STAGING_CONTAINER = "contract-staging"
API_VERSION = "2025-05-01-preview"


# ── Azure CU Client (copied exactly from Azure's sample) ─────────────────────

class AzureContentUnderstandingClient:
    def __init__(self, endpoint: str, api_version: str, subscription_key: str):
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version
        self._headers = {
            "Ocp-Apim-Subscription-Key": subscription_key,
            "x-ms-useragent": "contract-pipeline",
        }
        self._logger = logging.getLogger(__name__)

    def begin_analyze(self, analyzer_id: str, file_location: str):
        """Submit file or URL for analysis."""
        if Path(file_location).exists():
            # Local file — send as raw bytes
            with open(file_location, "rb") as f:
                data = f.read()
            headers = {"Content-Type": "application/octet-stream"}
            headers.update(self._headers)
            response = requests.post(
                url=self._get_analyze_url(analyzer_id),
                headers=headers,
                data=data,
            )
        elif file_location.startswith("http"):
            # URL (blob SAS URL) — send as JSON
            headers = {"Content-Type": "application/json"}
            headers.update(self._headers)
            response = requests.post(
                url=self._get_analyze_url(analyzer_id),
                headers=headers,
                json={"url": file_location},
            )
        else:
            raise ValueError(f"Invalid file location: {file_location}")

        response.raise_for_status()
        self._logger.info(f"[CU] Submitted {file_location} to {analyzer_id}")
        return response

    def poll_result(self, response, timeout_seconds=120, polling_interval_seconds=2):
        """Poll until job completes. Returns full result dict."""
        operation_location = response.headers.get("operation-location", "")
        if not operation_location:
            raise ValueError("No operation-location in response headers")

        headers = {"Content-Type": "application/json"}
        headers.update(self._headers)

        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise TimeoutError(f"CU job timed out after {timeout_seconds}s")

            poll_response = requests.get(operation_location, headers=self._headers)
            poll_response.raise_for_status()
            result = poll_response.json()
            status = result.get("status", "").lower()

            if status == "succeeded":
                self._logger.info(f"[CU] Completed in {elapsed:.1f}s")
                return result
            elif status == "failed":
                raise RuntimeError(f"[CU] Job failed: {result}")
            else:
                self._logger.info(f"[CU] In progress... ({elapsed:.0f}s)")

            time.sleep(polling_interval_seconds)

    def _get_analyze_url(self, analyzer_id: str) -> str:
        return (
            f"{self._endpoint}/contentunderstanding/analyzers"
            f"/{analyzer_id}:analyze"
            f"?api-version={self._api_version}&stringEncoding=utf16"
        )


# ── Handler entrypoint ────────────────────────────────────────────────────────

def handle_pdf(
    file_path: str,
    contract_type: Literal["nda", "sow", "both", "auto"] = "auto",
    upload_to_blob: bool = True,
) -> list[dict]:
    """
    Process a PDF through the CU analyzer pipeline.
    Returns list of raw extraction dicts, one per analyzer run.
    """
    log.info(f"[PDF Handler] Processing: {file_path}")

    endpoint = os.getenv("AZURE_CU_ENDPOINT")
    key = os.getenv("AZURE_CU_KEY")

    if not endpoint or not key:
        raise EnvironmentError("AZURE_CU_ENDPOINT and AZURE_CU_KEY must be set in .env")

    client = AzureContentUnderstandingClient(endpoint, API_VERSION, key)

    # Upload to blob if requested, otherwise send local file directly
    if upload_to_blob:
        from normalization.blob_uploader import upload_to_blob as do_upload
        file_location = do_upload(file_path, container=BLOB_STAGING_CONTAINER)
        log.info(f"[PDF Handler] Uploaded to blob: {file_location}")
    else:
        file_location = file_path  # send local file directly — works too

    results = []

    # Always run deal-intake first
    deal_result = run_cu_analyzer(client, CU_ANALYZER_IDS["deal_intake"], file_location, "deal_intake")
    results.append(deal_result)

    # Auto-detect contract type if needed
    if contract_type == "auto":
        contract_type = _detect_contract_type(deal_result)
        log.info(f"[PDF Handler] Detected type: {contract_type}")

    # Run NDA analyzer if needed
    if contract_type in ("nda", "both"):
        nda_result = run_cu_analyzer(
            client, CU_ANALYZER_IDS["nda"], file_location, "nda"
        )
        results.append(nda_result)

    # Run SOW analyzer if needed
    if contract_type in ("sow", "both"):
        sow_result = run_cu_analyzer(
            client, CU_ANALYZER_IDS["sow"], file_location, "sow"
        )
        results.append(sow_result)

    return results

def run_cu_analyzer(client, analyzer_id: str, file_location: str, source_label: str) -> dict:
    try:
        response = client.begin_analyze(analyzer_id, file_location)
        result = client.poll_result(response)
    except Exception as e:
        log.error(f"[CU] API call failed for {source_label}: {e}")
        return {"_source": source_label, "_analyzerUsed": analyzer_id, "_error": str(e), "_confidence": 0.0}

    try:
        extracted = _parse_cu_result(result, source_label)
    except Exception as e:
        log.error(f"[CU] Parse failed for {source_label}: {e}")
        import traceback
        traceback.print_exc()
        extracted = {"_parseError": str(e), "_confidence": 0.0}

    extracted["_source"] = source_label
    extracted["_analyzerUsed"] = analyzer_id
    log.info(f"[CU] {source_label} done — _source={extracted.get('_source')}, confidence={extracted.get('_confidence')}")
    return extracted

def _split_string_deliverables(value) -> list:
    """Split string deliverables into a clean list.
    SOW returns deliverables as a plain string with \n\n separators.
    deal_intake returns as CU array — this handles the string case.
    """
    if isinstance(value, str):
        items = [
            item.strip()
            for item in value.replace("\n\n", "\n").split("\n")
            if item.strip()
        ]
        return items
    return value

def _extract_derived_fields(extracted: dict) -> dict:
    """
    Extract fields that CU buries in nested structures.
    """
    # Pull NDA execution date from nextSteps
    next_steps = extracted.get("nextSteps", [])
    for step in next_steps:
        if isinstance(step, dict):
            obj = step.get("valueObject", {})
            action = obj.get("action", {}).get("valueString", "").lower()
            due_date = obj.get("dueDate", {}).get("valueDate", "")
            if "nda" in action and "template" in action and due_date:
                extracted["ndaTargetExecutionDate"] = due_date
                break

    # ── Unwrap nested array fields ───────────────────────────────────
    array_fields = ["inScope", "outOfScope", "nextSteps", 
                    "participants", "requestedDocuments", "invoiceTriggers"]
    
    for field in array_fields:
        val = extracted.get(field)
        if isinstance(val, list):
            extracted[field] = _unwrap_cu_array(val)

    # Split string-based deliverables (SOW returns these as plain strings)
    for field in ("deliverables", "inScopeItems", "milestones"):
        val = extracted.get(field)
        if isinstance(val, str) and val:
            extracted[field] = _split_string_deliverables(val)

    return extracted

def _parse_cu_result(result: dict, source_label: str) -> dict:
    """
    Parse CU response into flat field dict.
    Correctly reads per-field confidence scores.
    """
    extracted = {"_confidence": 0.0, "_fieldConfidence": {}}

    try:
        contents = result.get("result", {}).get("contents", [])
        if not contents:
            log.warning(f"[CU] No contents in result for {source_label}")
            return extracted

        fields = contents[0].get("fields", {})
        confidences = []

        for field_name, field_data in fields.items():
            # Unwrap the value
            value = (
                field_data.get("valueString")
                or field_data.get("valueNumber")
                or field_data.get("valueArray")
                or field_data.get("valueObject")
                or field_data.get("content")
            )
            if value is not None:
                extracted[field_name] = value

            # Read per-field confidence
            confidence = field_data.get("confidence")
            if confidence is not None:
                extracted["_fieldConfidence"][field_name] = confidence
                confidences.append(confidence)

        # Overall confidence = average of all field confidences
        if confidences:
            extracted["_confidence"] = round(
                sum(confidences) / len(confidences), 3
            )

    except Exception as e:
        log.error(f"[CU] Failed to parse result: {e}")
    extracted = _extract_derived_fields(extracted)
    return extracted

def _detect_contract_type(deal_intake_result: dict) -> Literal["nda", "sow", "both", "unknown"]:
    doc_types = str(deal_intake_result.get("requestedDocumentTypes", "")).lower()
    nda_required = str(deal_intake_result.get("ndaRequired", "")).lower()

    has_nda = "nda" in doc_types or nda_required == "yes"
    has_sow = "sow" in doc_types

    if has_nda and has_sow:
        return "both"
    if has_nda:
        return "nda"
    if has_sow:
        return "sow"
    return "unknown"

def _unwrap_cu_array(raw_array: list) -> list:
    result = []
    for item in raw_array:
        if not isinstance(item, dict):
            result.append(str(item).lstrip(". ").strip())
            continue

        obj = item.get("valueObject", {})

        for key in ("item", "text", "value", "description", "deliverable"):
            if key in obj:
                val = obj[key]
                text = (
                    val.get("valueString")
                    or val.get("content")
                    or str(val)
                )
                if text:
                    text = text.lstrip(". ").strip()
                    if text:
                        result.append(text)
                    break
        else:
            for val in obj.values():
                if isinstance(val, dict):
                    text = val.get("valueString") or val.get("content")
                    if text:
                        text = text.lstrip(". ").strip()
                        if text:
                            result.append(text)
                        break

    return result

    """
    Unwrap CU nested array format into a flat list of strings.
    CU returns arrays as: [{'type': 'object', 'valueObject': {'item': {'valueString': '...'}}}]
    """
    result = []
    for item in raw_array:
        if not isinstance(item, dict):
            result.append(str(item))
            continue

        obj = item.get("valueObject", {})

        # Try common field names CU uses inside array objects
        for key in ("item", "text", "value", "description", "deliverable"):
            if key in obj:
                val = obj[key]
                text = (
                    val.get("valueString")
                    or val.get("content")
                    or str(val)
                )
                if text:
                    result.append(text)
                    break
        else:
            # Fallback — just grab first string value found
            for val in obj.values():
                if isinstance(val, dict):
                    text = val.get("valueString") or val.get("content")
                    if text:
                        result.append(text)
                        break

    return result