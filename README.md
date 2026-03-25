# Contract Intelligence Platform

A production-grade pipeline that transforms unstructured contract documents — PDFs, Word docs, emails, and audio recordings — into standardised NDA and SOW PDFs using Azure AI services.

---

## What it does

```
Input (PDF / DOCX / EML / MP3 / WAV / M4A)
          ↓
Normalization layer
(pdf_handler / docx_handler / email_handler / audio_handler)
          ↓
Per‑modality extraction
  • PDF/DOCX → Azure Content Understanding (3 analyzers)
  • Audio → Speech (SDK or Batch) → LLM extractor (llm_audio)
          ↓
Mapping matrix → canonical fields
(canonical/mapping-matrix.yaml)
          ↓
Merge engine → conflict resolution & precedence
(orchestration/functions/merge_engine.py)
          ↓
Canonical JSON (single source of truth)
          ↓
PDF Generator → NDA / SOW auto-render
(generation/generate_contract_pdf.py)
          ↓
One‑shot orchestrators
  • run_pipeline.py (PDF/DOCX/EML)
  • run_audio_pipeline.py (Audio E2E)
          ↓
FastAPI (optional) – async jobs, file upload/download
(api.py)
```

---

## Architecture

### Normalisation layer (`normalization/`)

Each handler converts a raw input file into a list of extraction dicts. All handlers produce the same shape so the rest of the pipeline is modality-agnostic.

| Handler | Input | Method |
|---|---|---|
| `pdf_handler.py` | `.pdf` | Azure Content Understanding |
| `docx_handler.py` | `.docx` `.doc` | Azure Content Understanding |
| `email_handler.py` | `.eml` | Azure Content Understanding / text |
| `audio_handler.py` | `.mp3` `.wav` `.m4a` | Azure Speech → GPT-4o-mini |

The router (`normalization/__init__.py`) dispatches by file extension — `run_pipeline.py` calls `normalize(file_path)` and never needs to know the modality.

### Audio path in detail

```
Audio file
    ↓
Upload to Azure Blob Storage (container: audio-staging)
    ↓
File < 5 MB?  →  Azure Speech SDK  (real-time, synchronous)
File ≥ 5 MB?  →  Azure Speech REST (batch, async)
          - Diarization enabled only for mono
          - Stereo files are downmixed or diarization disabled automatically
(note: “Azure Speech Batch does not support diarization for stereo audio.”)
    ↓
Transcript text
    ↓
GPT-4o-mini  (system: deterministic JSON extractor)
    ↓
Extraction dict  (_source: "llm_audio")
    ↓
Same mapping matrix as PDF/DOCX
```

### Analyzers (`analyzers/`)

Three Azure Content Understanding analyzer schemas, each targeting a document type:

- **deal-intake** — general contract metadata (parties, dates, values)
- **nda** — NDA-specific fields (confidentiality term, governing law, disclosing party)
- **sow** — SOW-specific fields (scope, deliverables, payment terms, milestones)

### Canonical schema (`canonical/`)

All extraction results are normalised to a single schema defined in `contract-package.schema.json`. The `field-dictionary.md` documents every field. The `mapping-matrix.yaml` maps analyzer output keys to canonical field names with precedence rules when multiple analyzers extract the same field.

### Orchestration (`orchestration/functions/`)

| File | Role |
|---|---|
| `run_pipeline.py` | Top-level coordinator — calls normalise → analyze → merge → canonical |
| `map_to_canonical.py` | Applies mapping matrix to raw extractions |
| `merge_engine.py` | Resolves conflicts between multiple extractions using precedence rules |

### Generation (`generation/`)

`The PDF generator (generation/generate_contract_pdf.py) uses ReportLab to build fully styled NDA/SOW PDFs:

Navy cover page
Status banner
Dynamic clause rendering
Milestones, tables, obligations, exceptions
Signature block
Appendix: missing fields, conflicts, provenance

It takes canonical JSON only — no docx template required.

---

## API reference

Base URL (local): `http://localhost:8000`
Auth: `X-API-Key` header required on all endpoints except `/health`.

### `POST /analyze`

Upload a file and start the pipeline.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "X-API-Key: your_key" \
  -F "file=@contract.pdf" \
  -F "contract_type=auto"
```

Response:
```json
{
  "job_id": "d93f35f3-64d4-4a6a-a4ff-21f1e8c4ff50",
  "status": "queued",
  "message": "Pipeline started. Poll /jobs/{job_id} for status.",
  "poll_url": "/jobs/d93f35f3-..."
}
```

Supported file types: `.pdf` `.docx` `.doc` `.eml` `.mp3` `.wav` `.m4a`
`contract_type` values: `nda` | `sow` | `auto`

### `GET /jobs/{job_id}`

Poll job status.

```bash
curl http://localhost:8000/jobs/d93f35f3-... \
  -H "X-API-Key: your_key"
```

Status values:

| Status | Meaning |
|---|---|
| `queued` | Waiting to start |
| `processing` | Pipeline running |
| `complete` | Done — download URLs included in response |
| `failed` | Error — see `error` field |

### `GET /download/{job_id}/nda`

Download the generated NDA PDF.

### `GET /download/{job_id}/sow`

Download the generated SOW PDF.

### `GET /jobs`

List all jobs and their statuses.

### `DELETE /jobs/{job_id}`

Delete a job and all associated files.

### `GET /health`

Health check — no auth required.

```json
{ "status": "ok", "version": "1.0.0", "time": "2026-03-24T09:01:12Z" }
```

---

## Setup

### Prerequisites

- Python 3.11+
- Azure subscription with the following resources provisioned:
  - Azure Content Understanding (Document Intelligence)
  - Azure Blob Storage
  - Azure OpenAI (with a `gpt-4o-mini` deployment)
  - Azure Speech Services

### Install dependencies

```bash
pip install -r requirements.txt
```

Key packages:
```
fastapi
uvicorn
python-multipart
python-dotenv
azure-ai-documentintelligence
azure-storage-blob
azure-cognitiveservices-speech
openai
slowapi
requests
```

### Configure environment

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

Required variables:

```env
# API auth
CONTRACT_API_KEY=your_strong_key_here

# Azure Content Understanding
AZURE_CU_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CU_KEY=your_cu_key

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STR=DefaultEndpointsProtocol=https;AccountName=...

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_openai_key
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Azure Speech Services
AZURE_SPEECH_KEY=your_speech_key
AZURE_SPEECH_REGION=swedencentral

# Speech Batch transcription (container SAS)
BATCH_USE_CONTAINER=true
AUDIO_CONTAINER_SAS=https://<account>.blob.core.windows.net/<container>?<sas_token>
```

### GPT-4o-mini system prompt

In Azure OpenAI Studio → your deployment → System message, set:

```
You are a structured contract-analysis model. Your primary job is to take
unstructured or messy text (including audio transcripts) and transform it
into a clean JSON object according to the schema provided in the user prompt.

Rules you must always follow:
* Return ONLY valid JSON. Never include explanations, markdown, or text outside JSON.
* Follow the exact field names and structure the user provides.
* Use null for missing or unknown fields.
* Dates must be normalized to YYYY-MM-DD when possible.
* Do not hallucinate facts; base all output on the given text.
* If parts of the input are unclear, infer carefully but do not invent details.
* Maintain stable, deterministic formatting.

You are not a chat assistant. You are a deterministic JSON extraction system.
Whatever the user prompt says takes highest priority.
```
### Analyzer Classification
```
Automatic NDA vs SOW Classification
After merging the canonical package, run_audio_pipeline.py automatically determines whether the output PDF should be:

NDA (if parties.ndaType == "NDA")
SOW (if strong signals in scope.* or commercials.*)
Can be overridden with --render nda|sow|both
```
Quick Examples:
```
# Audio → NDA PDF (auto)
python -m orchestration.functions.run_audio_pipeline --input meeting.m4a

# Audio → both NDA and SOW PDFs
python -m orchestration.functions.run_audio_pipeline --input meeting.m4a --render both

# PDF contract → canonical → NDA PDF
python -m orchestration.functions.run_pipeline --input contract.pdf --type nda
```

### Run locally

```bash
python api.py
```

API docs (Swagger UI): http://localhost:8000/docs

### Run tests

```bash
# Full API test suite
python test_api.py --file tests/fixtures/deal-intake-sample-structured.pdf

# SOW fixture
python test_api.py --file tests/fixtures/sow_email.pdf
```

---

## Project structure

```
contract-intelligence-platform/
│
├── analyzers/                      # Azure CU analyzer schemas
│   ├── deal-intake/
│   │   ├── samples/
│   │   ├── __init__.py
│   │   └── deal-intake-schema.json
│   ├── nda/
│   │   ├── samples/
│   │   ├── __init__.py
│   │   └── nda-extractor-enterprise-v1_*.json
│   └── sow/
│       ├── samples/
│       ├── __init__.py
│       └── sow-extractor-enterprise_*.json
│
├── canonical/                      # Canonical schema + mapping rules
│   ├── golden-test-cases/
│   ├── __init__.py
│   ├── contract-package.schema.json
│   ├── example-contract-package.json
│   ├── field-dictionary.md
│   ├── mapping-matrix.yaml
│   └── precedence-rules.yaml
│
├── config/
│   ├── __init__.py
│   └── azure_clients.py            # Azure service client factory
│
├── generation/                     # PDF generation
│   ├── clause-selection-rules.yaml
│   ├── generate_contract_pdf.py
│   ├── golden-template-prompt.md
│   └── output-contract-template.docx
│
├── normalization/                  # Input normalizers (all modalities)
│   ├── __init__.py                 # Modality router
│   ├── audio_handler.py            # Speech → GPT-4o-mini
│   ├── blob_uploader.py            # Azure Blob upload helper
│   ├── docx_handler.py             # DOCX → Azure CU
│   ├── email_handler.py            # EML → Azure CU / text
│   └── pdf_handler.py              # PDF → Azure CU
│
├── orchestration/
│   ├── functions/
│   │   ├── __init__.py
│   │   ├── map_to_canonical.py     # Applies mapping matrix
│   │   ├── merge_engine.py         # Conflict resolution
│   │   └── run_pipeline.py         # Top-level coordinator
(PDF/DOCX/EML)
│   │   └── run_audio_pipeline.py    # one‑shot audio 
│   └── __init__.py
│
├── search/                         # Index files for search/retrieval
│   ├── __init__.py
│   ├── clause-library-index.json
│   ├── contract-package-index.json
│   └── evidence-index.json
│
├── tests/
│   ├── expected-canonical-output/
│   ├── fixtures/
│   │   ├── deal-intake-sample-structured.pdf
│   │   └── sow_email.pdf
│   ├── golden-cases/
│   └── output/
│
├── validators/
│   ├── __init__.py
│   └── schema_validator.py
│
├── api.py                          # FastAPI application
├── test_api.py                     # API test suite
├── requirements.txt
├── .env                            # Your secrets (never commit)
├── .env.example                    # Template — safe to commit
└── README.md
```

---

## Security checklist

Before sharing or deploying this API:

- [ ] Replace the default `CONTRACT_API_KEY` in `.env` with a strong random key
- [ ] Add `.env` to `.gitignore` — **never commit secrets**
- [ ] Add `api_uploads/` and `api_outputs/` to `.gitignore` — these contain client documents
- [ ] Lock `allow_origins` in `api.py` CORS config to your actual frontend domain
- [ ] Rotate the `AZURE_CU_KEY` visible in your `.env` screenshots

`.gitignore` should include at minimum:
```
.env
api_uploads/
api_outputs/
__pycache__/
*.pyc
```

---

## Known limitations and next steps

### In-memory job store

`JOBS` in `api.py` is a Python dict — it resets every time the API restarts. Fine for local development. Before deploying to Azure Container Apps, swap it for SQLite (one afternoon) or Azure Table Storage (same effort, fully managed).

```python
# Quick SQLite swap — drop-in replacement for JOBS dict
# pip install tinydb
from tinydb import TinyDB
db = TinyDB("jobs.db")
JOBS = db.table("jobs")
```

### Audio file size limit

The current split point is 5 MB (roughly 30 minutes of speech). For very long recordings, increase `_BATCH_MAX_WAIT_SECONDS` in `audio_handler.py`.

### Deploying to Azure Container Apps

```bash
# 1. Build image
docker build -t contract-intel .

# 2. Push to Azure Container Registry
az acr build --registry yourregistry --image contract-intel .

# 3. Deploy
az containerapp create \
  --name contract-intel \
  --resource-group your-rg \
  --image yourregistry.azurecr.io/contract-intel \
  --env-vars @.env
```

### Adding a frontend

The API is fully documented at `/docs`. A React or Next.js frontend can integrate in a day — the only endpoints needed are `POST /analyze`, `GET /jobs/{id}`, and `GET /download/{id}/nda|sow`.

---

## How audio extraction works end to end

1. Client uploads `.mp3` / `.wav` / `.m4a` to `POST /analyze`
2. API saves file to `api_uploads/`, creates a job, returns `job_id`
3. Background task calls `run_pipeline(file_path)`
4. `normalize()` routes to `audio_handler.handle_audio()`
5. File uploaded to Azure Blob container `audio-staging`
6. File size determines transcription mode:
   - **< 5 MB** → Speech SDK continuous recognition (synchronous)
   - **≥ 5 MB** → Speech REST batch API (async, no speaker diarization)
7. Transcript sent to GPT-4o-mini with field extraction prompt
8. Result tagged `_source: "llm_audio"` and returned to pipeline
9. Mapping matrix + merge engine produce canonical JSON
10. PDF generator renders NDA and SOW from canonical JSON
11. Job status → `complete`, download URLs available

---

## Licence

Private. All rights reserved.
