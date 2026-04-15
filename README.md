# **Contract Intelligence Platform**

<https://github.com/JoshJaiswal/contract_golden_template/actions/workflows/tests.yml/badge.svg>

A production‑grade pipeline that converts unstructured contract documents — **PDFs, Word docs, emails, and audio recordings** — into standardized **NDA and SOW PDFs** using Azure AI services. Includes a full **Next.js workspace frontend**.

***

## **Pipeline Overview**

    Input (PDF / DOCX / EML / MP3 / WAV / M4A)
            ↓
    Normalization Layer (per‑modality handlers)
            ↓
    Per‑modality Azure Extraction
            ↓
    Mapping Matrix → Canonical Fields
            ↓
    Merge Engine → Conflict Resolution
            ↓
    Canonical JSON (source of truth)
            ↓
    PDF Generator (NDA / SOW)
            ↓
    FastAPI Backend
            ↓
    Next.js Frontend Workspace

***

# **Architecture**

## **Normalization Layer (`/normalization`)**

Each handler converts raw input into a standardized extraction structure.

| Handler            | Input Types        | Method                          |
| ------------------ | ------------------ | ------------------------------- |
| `pdf_handler.py`   | .pdf               | Azure Content Understanding     |
| `docx_handler.py`  | .docx / .doc       | Azure Content Understanding     |
| `email_handler.py` | .eml               | CU / text extraction            |
| `audio_handler.py` | .mp3 / .wav / .m4a | Azure Speech → GPT‑4o (chunked) |

The router dispatches based on file extension. `run_pipeline.py` never needs to know modality.

***

## **Audio Pipeline (Detailed)**

    Audio file
        ↓
    Azure Blob Storage (audio-staging)
        ↓
    File <5MB → Speech SDK (sync)
    File ≥5MB → Speech REST Batch (async)
        ↓
    Transcript (mono = diarization; stereo = auto-disable)
        ↓
    Chunked LLM Extraction
    (6000 chars/chunk + 800 overlap)
        ↓
    GPT‑4o JSON Extraction
        ↓
    Partial Chunks → Aggregation
        ↓
    40+ Canonical Fields Extracted
        ↓
    Extraction Dict (_source="llm_audio")

**Why chunked?**  
Long audio often exceeds model token limits; chunking with overlap prevents silent truncation.

***

## **LLM Model Version Note (Important)**

`gpt‑4o-mini (0125)` **was retired March 2026**.  
Update your `.env` to a supported deployment:

| Deployment                 | Notes                          |
| -------------------------- | ------------------------------ |
| `gpt‑4o-mini (2024-07-18)` | Direct replacement             |
| `gpt‑4o`                   | Better extraction, higher cost |

Only affects audio extraction — CU analyzers are unaffected.

***

# **Analyzers (`/analyzers`)**

Azure Content Understanding analyzers:

*   **deal-intake** — contract metadata
*   **nda** — NDA‑specific fields
*   **sow** — SOW‑specific fields

Independent of Azure OpenAI model versions.

***

# **Canonical Schema (`/canonical`)**

All extractions map into a unified schema defined in:

*   `contract-package.schema.json`
*   `mapping-matrix.yaml`

### **Precedence rules (1–6; higher wins):**

| Source       | Precedence |
| ------------ | ---------- |
| SOW Analyzer | 4–6        |
| NDA Analyzer | 4–5        |
| Deal Intake  | 4–5        |
| LLM Audio    | 2–3        |

***

# **Orchestration (`/orchestration/functions`)**

| File                    | Purpose                     |
| ----------------------- | --------------------------- |
| `run_pipeline.py`       | Full end‑to‑end coordinator |
| `run_audio_pipeline.py` | Audio-only workflow         |
| `map_to_canonical.py`   | Applies mapping matrix      |
| `merge_engine.py`       | Conflict merging logic      |

***

# **PDF Generation (`/generation`)**

Built with ReportLab:

*   Styled cover page
*   Clause rendering
*   Deliverables, milestones, tables
*   Signature blocks
*   Missing fields appendix
*   No DOCX template required (pure JSON → PDF)

***

# **Frontend (`/frontend`)**

Next.js 15 App Router workspace.

### Pages

*   `/` — Upload
*   `/jobs` — Dashboard
*   `/jobs/[jobId]` — Job workspace

### Tech Stack

**Next.js 15 · TS · Tailwind · Zustand · Sonner**

Frontend design:

*   URL = source of truth
*   Zustand stores **overrides + dismissed conflicts** only
*   `/api/*` proxies to FastAPI

***

# **API Reference**

Base URL (local): `http://localhost:8000`  
Auth: `X-API-Key` (except `/health`)

***

## **POST `/analyze`**

Start pipeline + upload file.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "X-API-Key: your_key" \
  -F "file=@contract.pdf" \
  -F "contract_type=auto"
```

### Response:

```json
{
  "job_id": "d93f35f3-64d4-4a6a-a4ff-21f1e8c4ff50",
  "status": "queued",
  "message": "Pipeline started. Poll /jobs/{job_id} for status.",
  "poll_url": "/jobs/d93f35f3-..."
}
```

### Supported types

`.pdf .docx .doc .eml .mp3 .wav .m4a`

***

## **GET `/jobs/{jobId}`**

Poll status:

| Status     | Meaning   |
| ---------- | --------- |
| queued     | Waiting   |
| processing | Running   |
| complete   | Done      |
| failed     | Has error |

***

## **POST `/jobs/{jobId}/regenerate`**

```json
{
  "overrides": {
    "legal.governingLaw": "Tamil Nadu, India",
    "commercials.paymentTerms": "Net 30"
  },
  "dismissed_fields": ["scope.outOfScope"]
}
```

***

## **Downloads**

*   `/download/{jobId}/nda`
*   `/download/{jobId}/sow`
*   `/download/{jobId}/canonical`
*   `/download/{jobId}/source`

***

# **Setup**

## Prerequisites

*   Python **3.11+**
*   Node **18+**
*   Azure:
    *   Content Understanding
    *   Blob Storage
    *   OpenAI (gpt‑4o or updated gpt‑4o‑mini)
    *   Speech Services (S0 tier recommended)

***

## Backend

```bash
pip install -r requirements.txt
cp .env.example .env
python api.py
```

Swagger UI → `http://localhost:8000/docs`

***

## Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend → `http://localhost:3000`

***

# **Environment Variables**

(Kept same content — cleaned formatting)

<details>
<summary>Click to expand</summary>

```bash
# API auth
CONTRACT_API_KEY=your_strong_key_here

# Azure Content Understanding
AZURE_CU_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_CU_KEY=your_cu_key

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STR=...

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_openai_key
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini

# Azure Speech
AZURE_SPEECH_KEY=your_speech_key
AZURE_SPEECH_REGION=swedencentral
SPEECH_ALLOW_BATCH=true
SPEECH_DIARIZATION=false
BATCH_USE_CONTAINER=true
AUDIO_CONTAINER_SAS=...

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your_strong_key_here
```

</details>

***

# **Testing**

### Pytest markers

| Marker        | Tests                      | Azure Required |
| ------------- | -------------------------- | -------------- |
| `unit`        | mapping, merge, validation | ❌              |
| `pdf`         | PDF generation             | ❌              |
| `golden`      | regression snapshots       | ❌              |
| `integration` | full pipeline              | ✅              |

### Commands

```bash
pytest -m unit -v
pytest -m pdf -v
pytest -m "golden and not integration" -v
pytest -m integration -v
```

***

# **Makefile Shortcuts**

```bash
make test
make test-all
make test-unit
make test-pdf
make test-golden
make generate-golden
```

***

# **Project Structure**

(Formatted tree preserved exactly — now readable)

    contract-intelligence-platform/
    ├── analyzers/
    │   ├── deal-intake/
    │   ├── nda/
    │   └── sow/
    ├── canonical/
    │   ├── contract-package.schema.json
    │   ├── mapping-matrix.yaml
    │   ├── field-dictionary.md
    │   └── precedence-rules.yaml
    ├── config/
    │   └── azure_clients.py
    ├── frontend/
    │   ├── app/
    │   ├── components/
    │   ├── hooks/
    │   ├── lib/
    │   ├── store/
    │   └── next.config.js
    ├── generation/
    │   └── generate_contract_pdf.py
    ├── normalization/
    ├── orchestration/
    ├── tests/
    ├── validators/
    ├── api.py
    └── README.md

***

# **Known Limitations & Next Steps**

*   Job store — Azure Cosmos DB (NoSQL, serverless)
*   Jobs persist across API restarts and are queryable by status. Partition key is job_id.
*   Audio split point at 5MB
*   Chunked audio extraction logic
*   Update OpenAI deployments as models retire

***

# **Deployment (Azure Container Apps)**

```bash
docker build -t contract-intel .
az acr build --registry <registry> --image contract-intel .
az containerapp create --name contract-intel \
   --resource-group <rg> \
   --image <registry>.azurecr.io/contract-intel \
   --env-vars @.env
```

Frontend → deploy to Azure Static Web Apps or Vercel.

***

# **Security Checklist**

*   Replace default API key
*   Never commit `.env`
*   Lock CORS origins
*   Rotate any exposed keys
*   Use Key Vault in production

***

# **CI**

GitHub Actions runs:

*   unit
*   pdf
*   golden

Integration is skipped (requires Azure).

***

# **License**

**Private. All rights reserved.**

# Checking PR AND tests
