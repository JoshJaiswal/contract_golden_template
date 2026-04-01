"""
audio_handler.py
────────────────
Handles audio inputs (.mp3, .wav, .m4a) by:
  1. Uploading audio to Azure Blob Storage (for batch mode)
  2. Transcribing via Azure Speech Services
     - Real-time SDK  → files under ~5 MB (short calls) or when batch is disabled
     - Batch REST API → long recordings / compressed formats when available
  3. Sending transcript to GPT-4o for contract field extraction
  4. Returning a canonical-shaped extraction result

Notes you should know:
- Batch transcription requires a Standard (S0) Speech resource tier.
  On Free (F0), batch calls will be rejected by the service.
- The real-time SDK can read compressed files (mp3/m4a/mp4) only if the
  machine has GStreamer visible on PATH. WAV/PCM works natively.

Env switches:
- SPEECH_ALLOW_BATCH=true|false   # set to false on F0 during testing
"""

import json
import logging
import os
import time
import re
import threading
from pathlib import Path
from typing import Literal

import requests
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  # loads .env from your project root
_ENABLE_DIARIZATION = os.getenv("SPEECH_DIARIZATION", "false").strip().lower() in {"1","true","yes","y"}

log = logging.getLogger(__name__)

# Blob container for audio files (separate from contract docs)
AUDIO_BLOB_CONTAINER = "audio-staging"

# Batch transcription polling settings
_BATCH_POLL_INTERVAL_SECONDS = 10
_BATCH_MAX_WAIT_SECONDS = 600  # 10 minutes max

# Allow batch? (Disable on Free tier for testing)
_ALLOW_BATCH = os.getenv("SPEECH_ALLOW_BATCH", "true").strip().lower() in {"1", "true", "yes", "y"}

# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def handle_audio(
    file_path: str,
    contract_type: Literal["nda", "sow", "auto"] = "auto",
    upload_to_blob: bool = True,
) -> list[dict]:
    """
    Transcribe audio and extract contract fields.

    Args:
        file_path:      Local path to audio file (.mp3, .wav, .m4a).
        contract_type:  Hint for LLM extraction prompt.
        upload_to_blob: Upload audio to Blob before transcription.
                        Required for batch mode; set False only in tests.

    Returns:
        List with a single extraction dict tagged "_source": "llm_audio".
        Shape matches CU analyzer outputs so the mapping matrix works
        identically for audio as for PDF/DOCX.
    """
    log.info(f"[Audio] Processing: {Path(file_path).name}")

    # ── Step 1: Upload to Blob (needed for batch transcription) ───────────────
    audio_blob_url = None
    if upload_to_blob:
        from normalization.blob_uploader import upload_to_blob as do_upload
        audio_blob_url = do_upload(file_path, container=AUDIO_BLOB_CONTAINER)
        log.info(f"[Audio] Uploaded to blob: {audio_blob_url}")

    # ── Step 2: Transcribe ────────────────────────────────────────────────────
    transcript = transcribe_audio(audio_blob_url or file_path, file_path)
    log.info(f"[Audio] Transcription complete — {len(transcript)} chars")

    if not transcript.strip():
        raise ValueError(
            "Transcription returned empty text. "
            "Check the audio file has speech and Speech Services is provisioned."
        )

    # ── Step 3: Extract contract fields via GPT-4o ───────────────────────
    extracted = _extract_from_transcript(transcript, contract_type)
    extracted["_source"] = "llm_audio"
    extracted["_originalPath"] = file_path
    extracted["_transcript"] = transcript  # preserved for audit/review

    log.info(f"[Audio] Extraction complete — contractType={extracted.get('contractType')}")
    return [extracted]


# ─────────────────────────────────────────────────────────────────────────────
# Transcription routing
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_audio(blob_url_or_path: str, local_path: str) -> str:
    """
    Route to real-time or batch transcription based on file size and extension.

    - Under 5 MB  → real-time SDK (instant, synchronous)
    - 5 MB+       → batch REST API (async) when allowed
    - Compressed formats (.m4a/.mp4/.aac) → prefer batch when allowed
    """
    file_size_mb = Path(local_path).stat().st_size / (1024 * 1024)
    log.info(
        f"[Audio] File size: {file_size_mb:.1f} MB — "
        f"using {'real-time' if file_size_mb < 5 else 'batch'} transcription"
    )

    ext = Path(local_path).suffix.lower()
    is_https = isinstance(blob_url_or_path, str) and blob_url_or_path.startswith("https://")

    # Prefer batch for compressed formats to avoid local decode dependencies
    if ext in {".m4a", ".mp4", ".aac"}:
        if not _ALLOW_BATCH:
            raise RuntimeError(
                "Compressed input detected but batch is disabled (SPEECH_ALLOW_BATCH=false). "
                "On Free (F0) tier, record or convert to WAV/PCM for real-time testing, "
                "or upgrade Speech to Standard (S0) to enable batch for compressed files."
            )
        if not is_https:
            raise ValueError(
                "Batch transcription requires an Azure Blob URL for compressed inputs. "
                "Set upload_to_blob=True or pass a blob URL directly."
            )
        log.info(f"[Audio] {ext} detected — forcing batch transcription")
        return _transcribe_batch(blob_url_or_path)

    # Size-based routing for non-compressed formats
    if file_size_mb < 5 or not _ALLOW_BATCH:
        return _transcribe_realtime(local_path)
    else:
        if not is_https:
            raise ValueError(
                "Batch transcription requires an Azure Blob URL. "
                "Set upload_to_blob=True or pass a blob URL directly."
            )
        return _transcribe_batch(blob_url_or_path)


# ─────────────────────────────────────────────────────────────────────────────
# Real-time transcription (Azure Speech SDK)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_realtime(file_path: str) -> str:
    """
    Transcribe using Azure Speech SDK with continuous recognition.

    WAV/PCM works out of the box. For MP3/M4A on Windows, the SDK requires
    GStreamer to decode compressed audio at runtime.
    """
    import azure.cognitiveservices.speech as speechsdk
    from config.azure_clients import get_speech_config

    speech_config = get_speech_config()
    audio_config = speechsdk.audio.AudioConfig(filename=file_path)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    # Collect all recognised segments
    all_text: list[str] = []
    done = threading.Event()

    def on_recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            segment = evt.result.text.strip()
            if segment:
                all_text.append(segment)
                log.debug(f"[Audio] Segment: {segment[:60]}...")

    def on_cancelled(evt):
        details = evt.result.cancellation_details
        if details.reason == speechsdk.CancellationReason.Error:
            log.error(f"[Audio] Speech recognition error: {details.error_details}")
        done.set()

    def on_session_stopped(evt):
        done.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_cancelled)
    recognizer.session_stopped.connect(on_session_stopped)

    recognizer.start_continuous_recognition()
    done.wait(timeout=300)  # 5-minute timeout for safety
    recognizer.stop_continuous_recognition()

    transcript = " ".join(all_text)

    if not transcript:
        raise RuntimeError(
            "Speech recognition returned no text. "
            "If you used MP3/M4A, install GStreamer or record WAV/PCM; "
            "also verify AZURE_SPEECH_KEY/REGION."
        )

    return transcript


# ─────────────────────────────────────────────────────────────────────────────
# Batch transcription (Azure Speech REST API)
# ─────────────────────────────────────────────────────────────────────────────

def _transcribe_batch(blob_url: str) -> str:
    """
    Transcribe using Azure Speech batch transcription REST API.

    Flow:
      1. POST /transcriptions        → submit job, get job URL
      2. GET  /transcriptions/{id}   → poll until Succeeded/Failed
      3. GET  /transcriptions/{id}/files → get result file URLs
      4. GET  result file URL        → download JSON, parse display text
    """
    key, region = _get_speech_rest_credentials()
    base_url = f"https://{region}.api.cognitive.microsoft.com/speechtotext/v3.1"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
    }

    import os

    use_container = os.getenv("BATCH_USE_CONTAINER", "false").strip().lower() in {"1","true","yes","y"}
    if use_container:
        payload = {
            "contentContainerUrl": os.getenv("AUDIO_CONTAINER_SAS"),
            "locale": "en-IN",  # or en-US if you prefer
            "displayName": f"contract-intel-{int(time.time())}",
            "properties": {
                "diarizationEnabled": _ENABLE_DIARIZATION,
                "wordLevelTimestampsEnabled": False,
                "punctuationMode": "DictatedAndAutomatic",
                "profanityFilterMode": "Masked",
                "timeToLive": "PT48H",  # keep a TTL; current REST examples require/recommend it
            },
        }
    else:
        payload = {
            "contentUrls": [blob_url],
            "locale": "en-IN",
            "displayName": f"contract-intel-{int(time.time())}",
            "properties": {
                "diarizationEnabled": _ENABLE_DIARIZATION,
                "wordLevelTimestampsEnabled": False,
                "punctuationMode": "DictatedAndAutomatic",
                "profanityFilterMode": "Masked",
                "timeToLive": "PT48H",
            },
        }
    
    log.info("[Audio] Submitting batch transcription job...")
    resp = requests.post(f"{base_url}/transcriptions", headers=headers, json=payload)
    if not resp.ok:
        raise RuntimeError(
            f"Batch transcription submit failed ({resp.status_code}): {resp.text}"
        )

    job_url = resp.json()["self"]
    job_id = job_url.split("/")[-1]
    log.info(f"[Audio] Batch job submitted: {job_id}")

    # ── Poll for completion ────────────────────────────────────────────────────
    elapsed = 0
    while elapsed < _BATCH_MAX_WAIT_SECONDS:
        time.sleep(_BATCH_POLL_INTERVAL_SECONDS)
        elapsed += _BATCH_POLL_INTERVAL_SECONDS

        status_resp = requests.get(job_url, headers=headers)
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status = status_data.get("status", "")

        log.info(f"[Audio] Batch job status ({elapsed}s): {status}")

        if status == "Succeeded":
            break
        elif status == "Failed":
            # Try to surface the server's detailed failure report (if any)
            try:
                files_resp = requests.get(f"{job_url}/files", headers=headers)
                if files_resp.ok:
                    for f in files_resp.json().get("values", []):
                        kind = f.get("kind", "")
                        if "Report" in kind or kind == "TranscriptionReport":
                            rep = requests.get(f["links"]["contentUrl"])
                            if rep.ok:
                                log.error("[Audio] Batch failure report: %s", rep.text[:2000])
                                break
            except Exception:
                pass  # don't hide the main error

            error = status_data.get("properties", {}).get("error", {})
            raise RuntimeError(
                f"Batch transcription failed: {error.get('message', 'unknown error')}"
            )
    else:
        raise TimeoutError(
            f"Batch transcription timed out after {_BATCH_MAX_WAIT_SECONDS}s. "
            "Audio may be too long or Speech Services may be throttled."
        )

    # ── Retrieve result files ──────────────────────────────────────────────────
    files_resp = requests.get(f"{job_url}/files", headers=headers)
    files_resp.raise_for_status()
    files = files_resp.json().get("values", [])

    # Find the transcript result file (not the report file)
    result_url = next(
        (f["links"]["contentUrl"] for f in files if f.get("kind") == "Transcription"),
        None,
    )

    if not result_url:
        raise RuntimeError("Batch transcription succeeded but no result file found.")

    # ── Download and parse transcript JSON ────────────────────────────────────
    result_resp = requests.get(result_url)
    result_resp.raise_for_status()
    result_data = result_resp.json()

    # Extract display text from all recognised phrases, preserving speaker labels
    phrases = result_data.get("recognizedPhrases", [])
    lines: list[str] = []
    for phrase in phrases:
        best = (phrase.get("nBest") or [{}])[0]
        display = best.get("display", "").strip()
        if display:
            speaker = phrase.get("speaker")
            prefix = f"Speaker {speaker}: " if speaker else ""
            lines.append(f"{prefix}{display}")

    transcript = "\n".join(lines)

    # Clean up batch job (optional)
    try:
        requests.delete(job_url, headers={"Ocp-Apim-Subscription-Key": key})
        log.info(f"[Audio] Batch job {job_id} deleted after retrieval")
    except Exception:
        pass

    return transcript


def _get_speech_rest_credentials() -> tuple[str, str]:
    """Return (key, region) for Speech REST API calls."""
    from config.azure_clients import get_speech_endpoint
    return get_speech_endpoint()


# ─────────────────────────────────────────────────────────────────────────────
# GPT-4o extraction — chunked + aggregated
# ─────────────────────────────────────────────────────────────────────────────

_CHUNK_CHARS = 6000      # ~1500 tokens per chunk, well within context
_CHUNK_OVERLAP = 800     # overlap so sentences at boundaries aren't lost


def _extract_from_transcript(transcript: str, contract_type: str) -> dict:
    """
    Chunked extraction: split transcript → extract per chunk → aggregate.
    This ensures long recordings don't lose obligations, deliverables, etc.
    """
    from config.azure_clients import get_openai_client, get_openai_deployment

    client = get_openai_client()
    deployment = get_openai_deployment()

    chunks = _chunk_transcript(transcript, _CHUNK_CHARS, _CHUNK_OVERLAP)
    log.info(f"[Audio] Extracting from {len(chunks)} chunk(s) — total {len(transcript)} chars")

    partials: list[dict] = []
    for i, chunk in enumerate(chunks):
        log.info(f"[Audio] Processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        prompt = _build_transcript_prompt(chunk, contract_type, i + 1, len(chunks))
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_completion_tokens=2000,
            )
            raw = response.choices[0].message.content
            partial = json.loads(raw)
            partials.append(partial)
            log.info(f"[Audio] Chunk {i+1} extracted {sum(1 for v in partial.values() if v not in (None, [], ''))}" 
                     f" non-null fields")
        except (json.JSONDecodeError, Exception) as e:
            log.warning(f"[Audio] Chunk {i+1} failed: {e} — skipping")

    if not partials:
        raise ValueError("All extraction chunks failed — no data extracted from transcript")

    # Aggregate all partial results into one dict
    aggregated = _aggregate_extractions(partials)

    aggregated["_confidence"] = 0.75
    aggregated["_llmUsed"] = deployment
    return aggregated


def _chunk_transcript(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split transcript into overlapping chunks, breaking on sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # Try to break on a sentence boundary (. or \n) near the end
        if end < len(text):
            boundary = text.rfind('. ', start + chunk_size - 200, end)
            if boundary == -1:
                boundary = text.rfind('\n', start + chunk_size - 200, end)
            if boundary != -1:
                end = boundary + 1

        chunks.append(text[start:end].strip())
        start = end - overlap  # step back by overlap for continuity

    return [c for c in chunks if c.strip()]


def _aggregate_extractions(partials: list[dict]) -> dict:
    """
    Merge partial extraction dicts from multiple chunks.
    Strategy:
    - Scalar fields: first non-null value wins
    - Array fields: union all values, deduplicate
    - keyDiscussionPoints: always union
    """
    ARRAY_FIELDS = {
        "deliverables", "outOfScopeItems", "milestones", "obligations",
        "exceptions", "risks", "keyDiscussionPoints", "signatories",
        "warranties", "indemnities", "keyPersonnel", "dependencies",
        "assumptions", "constraints", "complianceStandards",
    }

    merged: dict = {}

    for partial in partials:
        for key, value in partial.items():
            if key.startswith("_"):
                continue

            if value is None or value == "" or value == []:
                continue

            if key in ARRAY_FIELDS:
                # Union lists, preserving order
                existing = merged.get(key) or []
                if isinstance(existing, str):
                    existing = [existing]
                if isinstance(value, str):
                    value = [value]
                # Deduplicate while preserving order
                seen = set(existing)
                for item in (value or []):
                    if item and item not in seen:
                        existing.append(item)
                        seen.add(item)
                merged[key] = existing
            else:
                # Scalar: first non-null wins
                if key not in merged:
                    merged[key] = value

    return merged


def _build_transcript_prompt(
    chunk: str,
    contract_type: str,
    chunk_num: int,
    total_chunks: int,
) -> str:
    """
    Full-coverage extraction prompt aligned to the mapping matrix.
    Field names match mapping-matrix.yaml sourceField for llm_audio.
    """
    chunk_note = (
        f"This is chunk {chunk_num} of {total_chunks} from a longer transcript. "
        "Extract whatever is mentioned in THIS chunk. Use null for anything not mentioned here."
        if total_chunks > 1 else
        "Extract all contract information from this transcript."
    )

    return f"""You are a contract analyst reviewing a recorded business call or meeting.
{chunk_note}

Contract type context: {contract_type}

Extract ALL of the following fields. Use null for anything not mentioned.
For arrays, extract every item mentioned — do NOT truncate lists.

Return ONLY a valid JSON object with EXACTLY these fields:

{{
  "clientName": "legal name of the client/customer organisation or null",
  "vendorName": "legal name of the vendor/service provider or null",
  "contractType": "NDA | SOW | both | unknown",

  "startDate": "YYYY-MM-DD or null",
  "endDate": "YYYY-MM-DD or null",
  "executionDate": "YYYY-MM-DD or null",

  "dealValue": "total contract value as number string e.g. '1800000' or null",
  "currency": "INR | USD | GBP | EUR or null",
  "paymentTerms": "payment schedule description or null",
  "pricingModel": "fixed-fee | time-and-materials | hybrid | subscription or null",
  "taxes": "tax clause description or null",
  "expenses": "expenses policy or null",

  "scopeOfWork": "1-3 sentence summary of the engagement objective or null",
  "deliverables": ["every deliverable mentioned, one per item"] or null,
  "outOfScopeItems": ["every out-of-scope item mentioned"] or null,
  "milestones": ["every milestone or timeline checkpoint mentioned"] or null,
  "assumptions": ["project assumptions mentioned"] or null,
  "constraints": ["constraints mentioned"] or null,
  "dependencies": ["dependencies mentioned"] or null,

  "confidentialityTerm": "duration of confidentiality obligation e.g. '3 years' or null",
  "obligations": ["specific confidentiality obligations mentioned"] or null,
  "exceptions": ["exceptions to confidentiality e.g. public domain info"] or null,

  "governingLaw": "governing jurisdiction e.g. 'Tamil Nadu, India' or null",
  "jurisdiction": "court jurisdiction or null",
  "disputeResolution": "arbitration/mediation/court process or null",
  "liabilityCap": "liability limitation description or null",
  "ipOwnership": "IP ownership terms or null",
  "warranties": ["warranties mentioned"] or null,
  "indemnities": ["indemnification terms mentioned"] or null,
  "terminationForConvenience": "termination for convenience terms or null",
  "terminationForCause": "termination for cause terms or null",

  "securityRequirements": "security obligations mentioned or null",
  "dataResidency": "data residency requirement e.g. 'India' or null",
  "complianceStandards": ["compliance standards e.g. ISO 27001, SOC2"] or null,
  "personalDataProcessing": "yes | no | null",
  "privacyRequirements": "privacy obligations described or null",

  "projectTimeline": "overall project duration or timeline description or null",
  "keyPersonnel": ["named individuals and their roles"] or null,
  "acceptanceCriteria": "how deliverables are accepted or null",
  "changeControl": "change request process or null",
  "governanceModel": "governance structure described or null",
  "issueEscalation": "escalation process described or null",

  "keyDiscussionPoints": ["important points not captured in fields above"] or null
}}

Rules:
- Use null (not empty string or []) for anything not mentioned in this chunk.
- Dates must be YYYY-MM-DD or null.
- dealValue must be digits only, no currency symbols.
- For ALL array fields: extract every item mentioned, never summarise into one item.
- If obligations or deliverables are discussed at length, list each one separately.
- Do not invent facts. Only extract what is explicitly stated or clearly implied.

Transcript chunk:
───────────────────────────────────────────────
{chunk}
───────────────────────────────────────────────

Return only the JSON object. No explanation, no markdown, no commentary.
"""