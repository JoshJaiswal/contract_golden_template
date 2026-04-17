"""
contract_assistant.py
──────────────────────
The Contract Intelligence AI Assistant.

Answers natural language questions about contracts by combining:
  1. Knowledge graph (Gremlin) — entity relationships, cross-contract queries
  2. Canonical JSON files      — detailed clause text for specific contracts

Uses GPT-4o (same deployment as the audio extraction pipeline) to:
  - Understand the question
  - Decide which data source(s) to query
  - Synthesise a grounded, cited answer

Entry point: ask(question, job_id=None, conversation_history=[])

Supports multi-turn conversation — pass conversation_history to maintain context.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Output dir — canonical JSONs are stored here after pipeline runs
OUTPUT_DIR = Path("api_outputs")


# ── Canonical JSON loader ──────────────────────────────────────────────────────

def load_canonical(job_id: str) -> Optional[dict]:
    """
    Load the canonical JSON for a specific job from disk.
    Returns None if not found.
    """
    canonical_path = OUTPUT_DIR / job_id / "canonical.json"
    if not canonical_path.exists():
        log.warning(f"[Assistant] Canonical not found for job {job_id}: {canonical_path}")
        return None
    with open(canonical_path, "r") as f:
        return json.load(f)


def load_all_canonicals() -> list[dict]:
    """
    Load canonical JSONs for all completed jobs.
    Used when the question is broad and not tied to a specific job.
    Returns list of (job_id, canonical) tuples as dicts.
    """
    results = []
    if not OUTPUT_DIR.exists():
        return results

    for job_dir in OUTPUT_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        canonical_path = job_dir / "canonical.json"
        if canonical_path.exists():
            try:
                with open(canonical_path, "r") as f:
                    data = json.load(f)
                data["_job_id"] = job_dir.name
                results.append(data)
            except Exception as e:
                log.warning(f"[Assistant] Could not load {canonical_path}: {e}")

    return results


# ── Context builder ────────────────────────────────────────────────────────────

def _build_canonical_context(canonical: dict, job_id: str) -> str:
    """
    Convert a canonical dict to a compact, readable context string for the LLM.
    Excludes provenance and raw conflicts to save tokens.
    """
    parties     = canonical.get("parties", {})
    dates       = canonical.get("dates", {})
    scope       = canonical.get("scope", {})
    conf        = canonical.get("confidentiality", {})
    commercials = canonical.get("commercials", {})
    security    = canonical.get("security", {})
    legal       = canonical.get("legal", {})
    gov         = canonical.get("projectGovernance", {})
    review      = canonical.get("review", {})
    missing     = canonical.get("missingFields", [])
    conflicts   = canonical.get("conflicts", [])

    client = (parties.get("client") or {}).get("name", "Unknown")
    vendor = (parties.get("vendor") or {}).get("name", "Unknown")

    lines = [
        f"=== CONTRACT: {job_id} ===",
        f"Client: {client}",
        f"Vendor: {vendor}",
        f"NDA Type: {parties.get('ndaType', '')}",
        "",
        f"Dates:",
        f"  Effective: {dates.get('effectiveDate', '')}",
        f"  Expiration: {dates.get('expirationDate', '')}",
        f"  Execution: {dates.get('executionDate', '')}",
        "",
        f"Scope: {scope.get('description', '')}",
        f"Deliverables: {json.dumps(scope.get('deliverables', []))}",
        f"Out of Scope: {json.dumps(scope.get('outOfScope', []))}",
        f"Milestones: {json.dumps(scope.get('milestones', []))}",
        "",
        f"Confidentiality Term: {conf.get('term', '')}",
        f"Confidentiality Obligations: {json.dumps(conf.get('obligations', []))}",
        f"Confidentiality Exceptions: {json.dumps(conf.get('exceptions', []))}",
        "",
        f"Commercials:",
        f"  Total Value: {commercials.get('totalValue', '')}",
        f"  Currency: {commercials.get('currency', '')}",
        f"  Payment Terms: {commercials.get('paymentTerms', '')}",
        f"  Pricing Model: {commercials.get('pricingModel', '')}",
        f"  Taxes: {commercials.get('taxes', '')}",
        f"  Expenses: {commercials.get('expenses', '')}",
        "",
        f"Security:",
        f"  Requirements: {security.get('requirements', '')}",
        f"  Data Residency: {security.get('dataResidency', '')}",
        f"  Compliance Standards: {security.get('complianceStandards', '')}",
        f"  Personal Data Processing: {security.get('personalDataProcessing', '')}",
        f"  Privacy Requirements: {security.get('privacyRequirements', '')}",
        "",
        f"Legal:",
        f"  Governing Law: {legal.get('governingLaw', '')}",
        f"  Jurisdiction: {legal.get('jurisdiction', '')}",
        f"  Dispute Resolution: {legal.get('disputeResolution', '')}",
        f"  Liability Cap: {legal.get('liabilityCap', '')}",
        f"  IP Ownership: {legal.get('ipOwnership', '')}",
        f"  Warranties: {legal.get('warranties', '')}",
        f"  Indemnities: {legal.get('indemnities', '')}",
        f"  Termination for Convenience: {legal.get('terminationForConvenience', '')}",
        f"  Termination for Cause: {legal.get('terminationForCause', '')}",
        f"  Service Levels: {legal.get('serviceLevels', '')}",
        f"  MSA Reference: {legal.get('msaReference', '')}",
        "",
        f"Project Governance:",
        f"  Timeline: {gov.get('projectTimeline', '')}",
        f"  Key Personnel: {gov.get('keyPersonnel', '')}",
        f"  Acceptance Criteria: {gov.get('acceptanceCriteria', '')}",
        f"  Change Control: {gov.get('changeControl', '')}",
        f"  Governance Model: {gov.get('governanceModel', '')}",
        f"  Issue Escalation: {gov.get('issueEscalation', '')}",
        f"  Dependencies: {gov.get('dependencies', '')}",
        f"  Assumptions: {gov.get('assumptions', '')}",
        f"  Constraints: {gov.get('constraints', '')}",
        "",
        f"Review Status: {review.get('status', '')}",
        f"Review Reasons: {json.dumps(review.get('reviewReason', []))}",
        f"Missing Fields: {json.dumps(missing[:20])}",  # cap at 20 to save tokens
        f"Conflict Count: {len(conflicts)}",
        f"Risks: {json.dumps(canonical.get('risks', []))}",
    ]

    return "\n".join(str(l) for l in lines)


def _build_graph_context(graph_results: dict) -> str:
    """
    Convert graph search results to a compact context string for the LLM.
    """
    intent  = graph_results.get("intent", "")
    results = graph_results.get("results", [])
    count   = graph_results.get("result_count", 0)

    if count == 0:
        return f"Graph query ({intent}): No results found."

    lines = [f"Graph query ({intent}): {count} result(s) found."]
    for r in results[:20]:  # cap at 20 to save tokens
        lines.append(json.dumps(r))

    return "\n".join(lines)


# ── System prompt loader ───────────────────────────────────────────────────────

def _load_system_prompt() -> str:
    prompt_path = Path(__file__).parent / "assistant_prompts.md"
    if prompt_path.exists():
        return prompt_path.read_text()
    # Fallback inline prompt if file not found
    return (
        "You are a Contract Intelligence Assistant. "
        "Answer questions about contracts using only the data provided. "
        "Never invent contract terms. Cite job_id or party names when answering."
    )


# ── Main ask function ──────────────────────────────────────────────────────────

def ask(
    question: str,
    job_id: Optional[str] = None,
    conversation_history: list[dict] = [],
) -> dict:
    """
    Main entry point. Answer a natural language question about contracts.

    Args:
        question:             The user's question.
        job_id:               Optional — scope to a specific contract job.
        conversation_history: Previous turns as [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        {
            "answer": str,                  # The assistant's answer
            "sources_used": list[str],      # Which data sources were queried
            "graph_results": dict | None,   # Raw graph query results (for debugging)
            "job_ids_referenced": list[str] # Which contracts were referenced
        }
    """
    from config.azure_clients import get_openai_client, get_openai_deployment
    from search.graph_search import graph_search

    client     = get_openai_client()
    deployment = get_openai_deployment()
    system_prompt = _load_system_prompt()

    context_parts  = []
    sources_used   = []
    graph_results  = None
    jobs_referenced = []

    # ── Step 1: Query knowledge graph ─────────────────────────────────────────
    # Always try the graph first — it's fast and handles cross-contract questions
    try:
        graph_results = graph_search(question)
        if graph_results["result_count"] > 0:
            context_parts.append("## Knowledge Graph Results\n" + _build_graph_context(graph_results))
            sources_used.append("knowledge_graph")

            # Extract any job_ids from graph results for follow-up canonical lookup
            for r in graph_results.get("results", []):
                jid = r.get("jobId") or r.get("entityId")
                if jid and jid not in jobs_referenced:
                    jobs_referenced.append(jid)

    except Exception as e:
        log.warning(f"[Assistant] Graph search failed: {e} — continuing with canonical only")
        context_parts.append(f"## Knowledge Graph\nGraph unavailable: {e}")

    # ── Step 2: Load canonical JSON(s) ────────────────────────────────────────
    # If job_id is specified → load that one
    # If graph found job_ids → load those
    # If neither → load all (for broad questions)

    canonical_job_ids = []
    if job_id:
        canonical_job_ids = [job_id]
    elif graph_results and graph_results.get("needs_canonical"):
        canonical_job_ids = jobs_referenced[:3]  # cap at 3 to avoid token overflow
    elif not graph_results or graph_results.get("result_count", 0) == 0:
        # No graph results — try to answer from all canonical JSONs
        all_canonicals = load_all_canonicals()
        if all_canonicals:
            context_parts.append("## All Contract Data")
            for c in all_canonicals[:5]:  # cap at 5 contracts
                jid = c.get("_job_id", "unknown")
                context_parts.append(_build_canonical_context(c, jid))
                if jid not in jobs_referenced:
                    jobs_referenced.append(jid)
            sources_used.append("canonical_json_all")

    # Load specific canonical(s) if identified
    for jid in canonical_job_ids:
        canonical = load_canonical(jid)
        if canonical:
            context_parts.append(f"## Contract Detail: {jid}\n" + _build_canonical_context(canonical, jid))
            sources_used.append(f"canonical_json:{jid}")
            if jid not in jobs_referenced:
                jobs_referenced.append(jid)

    # ── Step 3: Build messages for GPT-4o ─────────────────────────────────────
    context_text = "\n\n".join(context_parts) if context_parts else "No contract data available."

    messages = [{"role": "system", "content": system_prompt}]

    # Include conversation history for multi-turn support
    for turn in conversation_history[-6:]:  # last 3 exchanges (6 messages)
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})

    # Current question with context
    messages.append({
        "role": "user",
        "content": (
            f"## Available Contract Data\n\n{context_text}\n\n"
            f"## Question\n{question}\n\n"
            "Answer based only on the data above. "
            "If the data does not contain the answer, say so clearly. "
            "Cite contract job_id or party names when referencing specific contracts."
        )
    })

    # ── Step 4: Call GPT-4o ────────────────────────────────────────────────────
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_completion_tokens=1500,
            temperature=0.1,  # low temperature — factual, grounded answers only
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"[Assistant] GPT-4o call failed: {e}")
        answer = f"Sorry, I encountered an error generating an answer: {e}"

    return {
        "answer":            answer,
        "sources_used":      sources_used,
        "graph_results":     graph_results,
        "job_ids_referenced": jobs_referenced,
    }


# ── Conversation session helper ────────────────────────────────────────────────

class ContractConversation:
    """
    Stateful multi-turn conversation wrapper.
    Maintains history so each question has context from previous turns.

    Usage:
        conv = ContractConversation(job_id="abc-123")  # optional scope
        response = conv.ask("What are the payment terms?")
        response = conv.ask("And what about the governing law?")
    """

    def __init__(self, job_id: Optional[str] = None):
        self.job_id  = job_id
        self.history = []

    def ask(self, question: str) -> str:
        """Ask a question and return the answer string."""
        result = ask(
            question=question,
            job_id=self.job_id,
            conversation_history=self.history,
        )
        answer = result["answer"]

        # Append to history for next turn
        self.history.append({"role": "user",      "content": question})
        self.history.append({"role": "assistant",  "content": answer})

        return answer

    def reset(self):
        """Clear conversation history."""
        self.history = []