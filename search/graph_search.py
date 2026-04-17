"""
graph_search.py
────────────────
Translates natural language questions into Gremlin queries
and executes them against the Cosmos DB knowledge graph.

Used by the contract assistant to answer relational questions
like:
  "Which contracts involve Acme Corp?"
  "Show all deliverables due before March 2026"
  "Find all contracts that need review"

Two modes:
  1. intent_search(question) — GPT-4o picks the right query pattern
  2. Direct query helpers   — called when intent is already known
"""

import logging
import json
from pathlib import Path
from typing import Optional

from config.gremlin_client import run_gremlin_query

log = logging.getLogger(__name__)


# ── Intent patterns ────────────────────────────────────────────────────────────
# Maps intent name → Gremlin query template
# {param} placeholders are filled before execution

QUERY_PATTERNS = {

    # All contracts in the graph
    "list_all_contracts": (
        "g.V().hasLabel('Contract').valueMap(true)"
    ),

    # All contracts involving a named party (any role)
    "contracts_by_party": (
        "g.V().hasLabel('Party').has('name', '{party_name}')"
        ".in('HAS_PARTY').valueMap(true)"
    ),

    # All parties in a specific contract
    "parties_in_contract": (
        "g.V().has('Contract', 'entityId', '{job_id}')"
        ".out('HAS_PARTY').valueMap(true)"
    ),

    # All deliverables in a specific contract
    "deliverables_in_contract": (
        "g.V().has('Contract', 'entityId', '{job_id}')"
        ".out('HAS_DELIVERABLE').valueMap(true)"
    ),

    # All milestones in a specific contract
    "milestones_in_contract": (
        "g.V().has('Contract', 'entityId', '{job_id}')"
        ".out('HAS_MILESTONE').valueMap(true)"
    ),

    # All obligations in a specific contract
    "obligations_in_contract": (
        "g.V().has('Contract', 'entityId', '{job_id}')"
        ".out('HAS_OBLIGATION').valueMap(true)"
    ),

    # All contracts that need review
    "contracts_needing_review": (
        "g.V().hasLabel('Contract').has('reviewStatus', 'needs_review').valueMap(true)"
    ),

    # All contracts with a specific governing law
    "contracts_by_governing_law": (
        "g.V().hasLabel('Contract').has('governingLaw', '{governing_law}').valueMap(true)"
    ),

    # All parties across all contracts (unique names)
    "all_parties": (
        "g.V().hasLabel('Party').valueMap(true)"
    ),

    # All deliverables across all contracts
    "all_deliverables": (
        "g.V().hasLabel('Deliverable').valueMap(true)"
    ),

    # All milestones across all contracts
    "all_milestones": (
        "g.V().hasLabel('Milestone').valueMap(true)"
    ),

    # Full graph for one contract (vertices + edges)
    "full_contract_graph": (
        "g.V().has('Contract', 'entityId', '{job_id}')"
        ".union(__.identity(), __.out()).valueMap(true)"
    ),

    # Contracts where a party is specifically the client
    "contracts_by_client": (
        "g.V().hasLabel('Party').has('name', '{party_name}').has('role', 'client')"
        ".in('HAS_PARTY').valueMap(true)"
    ),

    # Contracts where a party is specifically the vendor
    "contracts_by_vendor": (
        "g.V().hasLabel('Party').has('name', '{party_name}').has('role', 'vendor')"
        ".in('HAS_PARTY').valueMap(true)"
    ),
}


# ── Intent classifier ──────────────────────────────────────────────────────────

def classify_intent(question: str) -> dict:
    """
    Use GPT-4o to classify a natural language question into a graph query intent
    and extract any parameters needed (party name, job_id, date, etc.)

    Returns:
        {
            "intent": "contracts_by_party",
            "params": { "party_name": "Acme Corp" },
            "needs_canonical": false,
            "canonical_question": ""
        }
    """
    from config.azure_clients import get_openai_client, get_openai_deployment

    client     = get_openai_client()
    deployment = get_openai_deployment()

    intents_list = "\n".join(f"  - {k}" for k in QUERY_PATTERNS.keys())

    prompt = f"""You are a query classifier for a contract knowledge graph assistant.

Available graph query intents:
{intents_list}
  - canonical_lookup  (requires reading the full canonical JSON for a job — use for detailed clause questions)
  - general_answer    (can be answered from graph results alone, no specific intent above matches)

User question: "{question}"

Classify this question. Return ONLY a JSON object with these fields:
{{
  "intent": "<one of the intent names above>",
  "params": {{
    "party_name": "<extracted party name or null>",
    "job_id": "<extracted job UUID or null>",
    "governing_law": "<extracted jurisdiction or null>"
  }},
  "needs_canonical": <true if detailed clause text is needed, false if graph structure is enough>,
  "canonical_question": "<rephrased question to ask about canonical JSON, or empty string>"
}}

Rules:
- If the question asks about a specific party by name, use contracts_by_party.
- If it asks about deliverables/milestones without a job_id, use all_deliverables/all_milestones.
- If it asks about review status, use contracts_needing_review.
- If it asks for payment terms, confidentiality text, governing law details, IP ownership — set needs_canonical=true.
- If a job_id (UUID) is mentioned, include it in params.job_id.
- Return only the JSON object, no explanation.
"""

    response = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_completion_tokens=300,
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning(f"[GraphSearch] Intent classification failed to parse JSON: {raw}")
        return {
            "intent": "list_all_contracts",
            "params": {},
            "needs_canonical": False,
            "canonical_question": "",
        }


# ── Query executor ─────────────────────────────────────────────────────────────

def execute_intent(intent: str, params: dict) -> list:
    """
    Execute the Gremlin query for a given intent with filled parameters.
    Returns list of vertex/edge dicts from the graph.
    """
    template = QUERY_PATTERNS.get(intent)
    if not template:
        log.warning(f"[GraphSearch] Unknown intent: {intent} — falling back to list_all_contracts")
        template = QUERY_PATTERNS["list_all_contracts"]

    # Fill parameters safely — escape single quotes
    filled_params = {
        k: str(v).replace("'", "\\'") if v else ""
        for k, v in params.items()
    }

    query = template
    for key, value in filled_params.items():
        query = query.replace(f"{{{key}}}", value)

    log.info(f"[GraphSearch] Executing intent={intent} query={query[:120]}...")

    try:
        results = run_gremlin_query(query)
        log.info(f"[GraphSearch] Got {len(results)} result(s)")
        return results
    except Exception as e:
        log.error(f"[GraphSearch] Gremlin query failed: {e}")
        return []


# ── Clean graph results for LLM consumption ───────────────────────────────────

def flatten_vertex(vertex: dict) -> dict:
    """
    Cosmos DB Gremlin returns values as lists e.g. {"name": ["Acme Corp"]}.
    Flatten to {"name": "Acme Corp"} for cleaner LLM consumption.
    """
    flat = {}
    for k, v in vertex.items():
        if k in ("id", "label"):
            flat[k] = v
        elif isinstance(v, list) and len(v) == 1:
            flat[k] = v[0]
        elif isinstance(v, list):
            flat[k] = v
        else:
            flat[k] = v
    return flat


def flatten_results(results: list) -> list:
    return [flatten_vertex(r) for r in results]


# ── Main search entry point ────────────────────────────────────────────────────

def graph_search(question: str) -> dict:
    """
    Main entry point for the assistant.
    Classifies the question, runs the graph query, returns structured results.

    Returns:
        {
            "intent": str,
            "params": dict,
            "results": list[dict],          # flattened graph vertices
            "needs_canonical": bool,
            "canonical_question": str,
            "result_count": int
        }
    """
    classification = classify_intent(question)
    intent   = classification.get("intent", "list_all_contracts")
    params   = classification.get("params", {})

    # canonical_lookup is a signal to the assistant, not a real Gremlin intent
    if intent == "canonical_lookup":
        return {
            "intent": "canonical_lookup",
            "params": params,
            "results": [],
            "needs_canonical": True,
            "canonical_question": classification.get("canonical_question", question),
            "result_count": 0,
        }

    raw_results  = execute_intent(intent, params)
    flat_results = flatten_results(raw_results)

    return {
        "intent":             intent,
        "params":             params,
        "results":            flat_results,
        "needs_canonical":    classification.get("needs_canonical", False),
        "canonical_question": classification.get("canonical_question", ""),
        "result_count":       len(flat_results),
    }


# ── Direct helper functions (called by graph endpoints in api.py) ──────────────

def search_contracts_by_party(party_name: str) -> list:
    results = execute_intent("contracts_by_party", {"party_name": party_name})
    return flatten_results(results)


def search_all_contracts() -> list:
    results = execute_intent("list_all_contracts", {})
    return flatten_results(results)


def search_contracts_needing_review() -> list:
    results = execute_intent("contracts_needing_review", {})
    return flatten_results(results)