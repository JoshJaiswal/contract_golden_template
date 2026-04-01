# Contract Intelligence Platform

![CI](https://github.com/JoshJaiswal/contract_golden_template/actions/workflows/tests.yml/badge.svg)

A production-grade pipeline that transforms unstructured contract documents — PDFs, Word docs, emails, and audio recordings — into standardised NDA and SOW PDFs using Azure AI services, with a full Next.js frontend workspace.

What it does
Input (PDF / DOCX / EML / MP3 / WAV / M4A)
          ↓
Normalization layer
(pdf_handler / docx_handler / email_handler / audio_handler)
          ↓
Per-modality extraction
  • PDF/DOCX/EML → Azure Content Understanding (3 analyzers)
  • Audio → Azure Speech (SDK or Batch) → GPT-4o LLM extractor (chunked)
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
FastAPI → async jobs, file upload/download
(api.py)
          ↓
Next.js Frontend → contract workspace, conflict resolution, downloads
(frontend/)
Architecture
Normalisation layer (normalization/)
Each handler converts a raw input file into a list of extraction dicts. All handlers produce the same shape so the rest of the pipeline is modality-agnostic.

Handler	Input	Method
pdf_handler.py	.pdf	Azure Content Understanding
docx_handler.py	.docx .doc	Azure Content Understanding
email_handler.py	.eml	Azure Content Understanding / text
audio_handler.py	.mp3 .wav .m4a	Azure Speech → GPT-4o (chunked)
The router (normalization/__init__.py) dispatches by file extension. run_pipeline.py calls normalize(file_path) and never needs to know the modality.

Audio pipeline in detail
Audio file
    ↓
Upload to Azure Blob Storage (container: audio-staging)
    ↓
File < 5 MB?  →  Azure Speech SDK  (real-time, synchronous)
File ≥ 5 MB?  →  Azure Speech REST (batch, async)
    - Diarization enabled only for mono
    - Stereo files: diarization disabled automatically
    - .m4a/.mp4/.aac always routed to batch (requires GStreamer otherwise)
    ↓
Full transcript text
    ↓
Chunked extraction (6000 chars / chunk, 800 char overlap)
    ↓
GPT-4o  (system: deterministic JSON extractor)
  - Each chunk extracted independently → partial JSON
  - Aggregation pass: scalar fields = first non-null wins
                      array fields  = union + deduplicate
    ↓
40+ canonical fields extracted (deliverables, obligations,
milestones, governing law, parties, commercials, security, etc.)
    ↓
Extraction dict  (_source: "llm_audio")
    ↓
Same mapping matrix as PDF/DOCX
Why chunked? A 10-minute call at 150 words/minute exceeds 12,000 characters. Single-pass extraction silently drops everything after the truncation point. Chunked extraction with overlap ensures obligations discussed at minute 2 and deliverables discussed at minute 8 are both captured.

Important — model version: The LLM extraction uses the deployment set in AZURE_OPENAI_DEPLOYMENT. gpt-4o-mini (version 0125) was retired end of March 2026. Update your .env to a current deployment — recommended options:

Deployment	Notes
gpt-4o-mini (version 2024-07-18)	Direct replacement, same cost
gpt-4o	Higher quality extraction, higher cost
This only affects audio extraction. Content Understanding analyzers are unaffected.

Analyzers (analyzers/)
Three Azure Content Understanding analyzer schemas, each targeting a document type:

deal-intake — general contract metadata (parties, dates, values, scope)
nda — NDA-specific fields (confidentiality term, governing law, disclosing party)
sow — SOW-specific fields (scope, deliverables, payment terms, milestones, governance)
These are completely independent of the OpenAI deployment and are unaffected by model version changes.

Canonical schema (canonical/)
All extraction results are normalised to a single schema defined in contract-package.schema.json. The mapping-matrix.yaml maps analyzer output keys to canonical field names with precedence rules when multiple analyzers extract the same field.

Precedence scale (1–6, higher = wins on conflict):

Source	Typical precedence
SOW analyzer	4–6
NDA analyzer	4–5
Deal intake analyzer	4–5
LLM audio	2–3
Orchestration (orchestration/functions/)
File	Role
run_pipeline.py	Top-level coordinator — calls normalise → analyze → merge → canonical
run_audio_pipeline.py	One-shot audio end-to-end
map_to_canonical.py	Applies mapping matrix to raw extractions
merge_engine.py	Resolves conflicts between multiple extractions using precedence rules
Generation (generation/)
The PDF generator (generation/generate_contract_pdf.py) uses ReportLab to build fully styled NDA/SOW PDFs:

Navy cover page
Status banner
Dynamic clause rendering
Milestones, tables, obligations, exceptions
Signature block
Appendix: missing fields, conflicts, provenance
Takes canonical JSON only — no DOCX template required.

Frontend (frontend/)
A Next.js 15 App Router frontend providing a full contract workspace:

/           → Upload page (drag-drop, contract type selector)
/jobs       → Dashboard (metrics panel, job list, status badges)
/jobs/[jobId] → Job workspace (tabs: Overview / Summary / Conflicts /
                Missing Fields / Source / Canonical JSON / Downloads)
Stack: Next.js 15 · TypeScript · Tailwind CSS · Zustand · Sonner (toasts)

Key design decisions:

URL is source of truth for active job — useParams() reads jobId, not Zustand
Zustand holds edit state only (overrides, dismissed conflicts)
API calls go through Next.js rewrites (/api/jobs/* → FastAPI)
Params are unwrapped with useParams() (Next.js 15 made params async)
API reference
Base URL (local): http://localhost:8000 Auth: X-API-Key header required on all endpoints except /health.

POST /analyze
Upload a file and start the pipeline.

curl -X POST http://localhost:8000/analyze \
  -H "X-API-Key: your_key" \
  -F "file=@contract.pdf" \
  -F "contract_type=auto"
Response:

{
  "job_id": "d93f35f3-64d4-4a6a-a4ff-21f1e8c4ff50",
  "status": "queued",
  "message": "Pipeline started. Poll /jobs/{job_id} for status.",
  "poll_url": "/jobs/d93f35f3-..."
}
Supported file types: .pdf .docx .doc .eml .mp3 .wav .m4a contract_type values: nda | sow | both | auto

GET /jobs/{job_id}
Poll job status.

Status	Meaning
queued	Waiting to start
processing	Pipeline running
complete	Done — download URLs included
failed	Error — see error field
POST /jobs/{job_id}/regenerate
Regenerate documents with field overrides and/or dismissed conflicts.

{
  "overrides": {
    "legal.governingLaw": "Tamil Nadu, India",
    "commercials.paymentTerms": "Net 30"
  },
  "dismissed_fields": ["scope.outOfScope"]
}
GET /download/{job_id}/nda
GET /download/{job_id}/sow
GET /download/{job_id}/canonical
GET /download/{job_id}/source
GET /jobs
DELETE /jobs/{job_id}
GET /health
No auth required.

{ "status": "ok", "version": "1.0.0", "time": "2026-04-01T00:00:00Z" }
Setup
Prerequisites
Python 3.11+
Node.js 18+ (for frontend)
Azure subscription with:
Azure Content Understanding (Document Intelligence)
Azure Blob Storage
Azure OpenAI (with a gpt-4o or gpt-4o-mini deployment — not the retired 0125 version)
Azure Speech Services (Standard S0 tier for batch/audio)
Backend
pip install -r requirements.txt
cp .env.example .env
# Fill in all values — see Environment Variables below
python api.py
Swagger UI: http://localhost:8000/docs

Frontend
cd frontend
npm install
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL and NEXT_PUBLIC_API_KEY
npm run dev
Frontend: http://localhost:3000

Environment variables
# ── API auth ──────────────────────────────────────────────────────
CONTRACT_API_KEY=your_strong_key_here

# ── Azure Content Understanding ───────────────────────────────────
AZURE_CU_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CU_KEY=your_cu_key

# ── Azure Blob Storage ────────────────────────────────────────────
AZURE_BLOB_CONNECTION_STR=DefaultEndpointsProtocol=https;AccountName=...

# ── Azure OpenAI ──────────────────────────────────────────────────
# IMPORTANT: Use a current deployment — gpt-4o-mini (0125) was retired March 2026
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_openai_key
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini   # must be version 2024-07-18 or later

# ── Azure Speech Services ─────────────────────────────────────────
# Standard (S0) tier required for batch transcription (audio ≥ 5 MB)
AZURE_SPEECH_KEY=your_speech_key
AZURE_SPEECH_REGION=swedencentral

# ── Speech options ────────────────────────────────────────────────
SPEECH_ALLOW_BATCH=true          # set false on Free (F0) tier
SPEECH_DIARIZATION=false         # true only for mono audio with multiple speakers
BATCH_USE_CONTAINER=true
AUDIO_CONTAINER_SAS=https://<account>.blob.core.windows.net/<container>?<sas_token>

# ── Frontend (.env.local) ─────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your_strong_key_here
GPT-4o system prompt
In Azure OpenAI Studio → your deployment → System message:

You are a structured contract-analysis model. Your primary job is to take
unstructured or messy text (including audio transcripts) and transform it
into a clean JSON object according to the schema provided in the user prompt.

Rules you must always follow:
* Return ONLY valid JSON. Never include explanations, markdown, or text outside JSON.
* Never return an empty response — always return a valid JSON object.
* Follow the exact field names and structure the user provides.
* Use null for missing or unknown fields.
* Dates must be normalized to YYYY-MM-DD when possible.
* Do not hallucinate facts; base all output on the given text.
* For array fields, extract every item — never truncate or summarise lists.
* Maintain stable, deterministic formatting.

You are not a chat assistant. You are a deterministic JSON extraction system.
Whatever the user prompt says takes highest priority.
Testing
Tests are grouped using pytest markers.

Test types
Marker	What it tests	Azure required
unit	Mapping transforms, merge engine, schema validation	No
pdf	ReportLab PDF rendering, NDA/SOW output	No
golden	Canonical output regression against frozen snapshots	No
integration	Full Azure-backed pipeline end-to-end	Yes
# Fast — no Azure needed
pytest -m unit -v
pytest -m pdf -v
pytest -m "golden and not integration" -v

# Full suite (requires .env with valid Azure keys)
pytest -m integration -v
Makefile shortcuts
make test          # unit + pdf + golden
make test-all      # everything including integration
make test-unit
make test-pdf
make test-golden
make generate-golden   # regenerate golden snapshots after intentional changes
Windows users without make: use pytest directly or run in Git Bash.

Regenerating golden snapshots
Run after intentionally changing mapping-matrix.yaml, merge_engine.py, contract-package.schema.json, or any extraction behavior:

make generate-golden
# or:
pytest -m integration -v --generate-golden
Project structure
contract-intelligence-platform/
│
├── analyzers/                      # Azure CU analyzer schemas
│   ├── deal-intake/
│   ├── nda/
│   └── sow/
│
├── canonical/                      # Canonical schema + mapping rules
│   ├── contract-package.schema.json
│   ├── mapping-matrix.yaml         # Source field → canonical path + precedence
│   ├── field-dictionary.md
│   └── precedence-rules.yaml
│
├── config/
│   └── azure_clients.py            # Azure service client factory
│
├── frontend/                       # Next.js 15 workspace
│   ├── app/
│   │   ├── page.tsx                # Upload page
│   │   ├── jobs/
│   │   │   ├── page.tsx            # Dashboard
│   │   │   └── [jobId]/page.tsx    # Job workspace
│   ├── components/
│   │   ├── layout/                 # AppShell, Header, NavTabs, Footer
│   │   ├── upload/                 # UploadDropzone, ContractTypeSelect
│   │   ├── dashboard/              # MetricsPanel, JobList, JobRow
│   │   ├── viewer/                 # ContractViewer, tabs, preview, JSON
│   │   ├── summary/                # SummarySection, SummaryRow
│   │   ├── conflicts/              # ConflictList, ConflictCard, ConflictResolver
│   │   ├── missing/                # MissingFieldTree, MissingFieldEditor
│   │   └── ui/                     # Button, Card, Badge, Input, Tabs, Toast
│   ├── hooks/
│   │   ├── useUploadJob.ts
│   │   ├── useJobPolling.ts        # Polls every 3s, stops on complete/failed
│   │   ├── useJobList.ts
│   │   └── useRegenerateJob.ts
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts           # Base fetch + X-API-Key injection
│   │   │   ├── jobs.ts             # All API functions
│   │   │   └── types.ts            # TypeScript types
│   │   └── format.ts               # extractSummarySections, extractConflicts,
│   │                               # extractMissingFields — aligned to canonical shape
│   ├── store/
│   │   └── useAppStore.ts          # Zustand: overrides + dismissedFields only
│   └── next.config.js              # Rewrites: /api/jobs/* → FastAPI
│
├── generation/
│   └── generate_contract_pdf.py    # ReportLab NDA/SOW renderer
│
├── normalization/
│   ├── __init__.py                 # Modality router
│   ├── audio_handler.py            # Speech → chunked GPT-4o extraction
│   ├── blob_uploader.py
│   ├── docx_handler.py
│   ├── email_handler.py
│   └── pdf_handler.py
│
├── orchestration/functions/
│   ├── run_pipeline.py
│   ├── run_audio_pipeline.py
│   ├── map_to_canonical.py
│   └── merge_engine.py
│
├── tests/
│   ├── fixtures/
│   ├── golden-cases/
│   └── output/
│
├── validators/
│   └── schema_validator.py
│
├── api.py                          # FastAPI application
├── requirements.txt
├── .env                            # Never commit
├── .env.example
└── README.md
Known limitations and next steps
In-memory job store
JOBS in api.py is a Python dict — it resets on every API restart. Fine for local development and demos. Before deploying, swap for SQLite or Azure Table Storage:

# Quick SQLite swap
from tinydb import TinyDB
db = TinyDB("jobs.db")
JOBS = db.table("jobs")
Audio file size
Current split point: 5 MB (~30 minutes). For longer recordings, increase _BATCH_MAX_WAIT_SECONDS in audio_handler.py.

Audio extraction field coverage
The LLM extraction prompt covers 40+ canonical fields including deliverables, obligations, milestones, governance, security, and legal terms. Chunked extraction (6000 chars/chunk, 800 char overlap) ensures long recordings don't silently drop fields mentioned in later segments.

OpenAI model version
gpt-4o-mini version 0125 was retired March 2026. Update AZURE_OPENAI_DEPLOYMENT in .env to version 2024-07-18 or switch to gpt-4o. No other code changes required — the deployment name is read from env at runtime.

Deployment (Azure Container Apps)
docker build -t contract-intel .
az acr build --registry yourregistry --image contract-intel .
az containerapp create \
  --name contract-intel \
  --resource-group your-rg \
  --image yourregistry.azurecr.io/contract-intel \
  --env-vars @.env
For the frontend, deploy to Azure Static Web Apps or Vercel. Set NEXT_PUBLIC_API_URL to your Container App URL and configure CORS in api.py to allow your frontend domain.

Security checklist
Before sharing or deploying:

 Replace default CONTRACT_API_KEY with a strong random key
 Add .env to .gitignore — never commit secrets
 Add api_uploads/ and api_outputs/ to .gitignore
 Lock allow_origins in api.py CORS config to your frontend domain
 Rotate any Azure keys visible in screenshots or logs
 Use Azure Key Vault for secrets in production
.gitignore minimum:

.env
api_uploads/
api_outputs/
__pycache__/
*.pyc
frontend/.next/
frontend/node_modules/
Continuous Integration
GitHub Actions runs on every push and pull request:

Unit tests (-m unit)
PDF tests (-m pdf)
Golden snapshot tests (-m "golden and not integration")
Integration tests are skipped in CI — they require live Azure credentials and are run manually.

Workflow file: .github/workflows/tests.yml

Licence
Private. All rights reserved.

