"""
graph_builder.py
─────────────────
Builds and queries the contract knowledge graph in Cosmos DB (Gremlin API).

Called at the end of run_pipeline.py after the canonical JSON is finalised.
Extracts named entities (parties, obligations, deliverables, etc.) from the
canonical dict and writes them as vertices + edges to the Gremlin graph.

Graph schema
────────────
Vertex labels : Contract | Party | Obligation | Deliverable | Milestone | Clause
Edge labels   : HAS_PARTY | HAS_OBLIGATION | HAS_DELIVERABLE | HAS_MILESTONE | HAS_CLAUSE

All vertex properties are stored as strings (Gremlin / Cosmos limitation).
"""

import logging
from config.gremlin_client import run_gremlin_query

log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe(value) -> str:
    """Escape single quotes and truncate long strings for Gremlin queries."""
    return str(value).replace("'", "\\'")[:250]


def _props_str(properties: dict) -> str:
    """Convert a dict to a chain of .property(...) calls for Gremlin."""
    return "".join(
        f".property('{_safe(k)}', '{_safe(v)}')"
        for k, v in properties.items()
        if v and str(v).strip()
    )


def upsert_vertex(label: str, entity_id: str, properties: dict) -> None:
    """
    Create or update a vertex.
    Uses coalesce(unfold(), addV(...)) pattern — safe for concurrent calls.
    """
    props = _props_str(properties)
    query = (
        f"g.V().has('{label}', 'entityId', '{_safe(entity_id)}')"
        f".fold()"
        f".coalesce("
        f"  unfold(){props},"
        f"  addV('{label}').property('entityId', '{_safe(entity_id)}'){props}"
        f")"
    )
    run_gremlin_query(query)


def upsert_edge(from_entity_id: str, to_entity_id: str, edge_label: str, properties: dict = {}) -> None:
    """
    Create an edge between two vertices if it doesn't already exist.
    """
    props = _props_str(properties)
    query = (
        f"g.V().has('entityId', '{_safe(from_entity_id)}').as('a')"
        f".V().has('entityId', '{_safe(to_entity_id)}').as('b')"
        f".coalesce("
        f"  __.select('a').outE('{edge_label}').where(inV().as('b')),"
        f"  addE('{edge_label}').from('a').to('b'){props}"
        f")"
    )
    run_gremlin_query(query)


# ── Main builder ───────────────────────────────────────────────────────────────

def build_graph_from_canonical(job_id: str, canonical: dict) -> None:
    """
    Traverse the canonical contract package and write all entities to the graph.

    Args:
        job_id:    Pipeline job ID — used as the Contract vertex entityId.
        canonical: Merged canonical dict produced by merge_engine.merge_results().
    """
    log.info(f"[GraphBuilder] Building graph for job {job_id}")

    # ── 1. Contract vertex ────────────────────────────────────────────────────
    dates       = canonical.get("dates", {})
    legal       = canonical.get("legal", {})
    review      = canonical.get("review", {})

    upsert_vertex("Contract", job_id, {
        "jobId":          job_id,
        "contractType":   canonical.get("_contractType", ""),
        "effectiveDate":  dates.get("effectiveDate", ""),
        "expirationDate": dates.get("expirationDate", ""),
        "governingLaw":   legal.get("governingLaw", ""),
        "reviewStatus":   review.get("status", ""),
    })

    # ── 2. Party vertices + HAS_PARTY edges ───────────────────────────────────
    parties = canonical.get("parties", {})
    for role in ("client", "vendor"):
        party_info = parties.get(role)
        if not party_info:
            continue
        party_name = (
            party_info.get("name", "").strip()
            if isinstance(party_info, dict)
            else str(party_info).strip()
        )
        if not party_name:
            continue

        party_id = f"{party_name.replace(' ', '_').lower()}_{role}"
        upsert_vertex("Party", party_id, {
            "name": party_name,
            "role": role,
        })
        upsert_edge(job_id, party_id, "HAS_PARTY", {"role": role})
        log.debug(f"[GraphBuilder] Party: {role} → {party_name}")

    # ── 3. Obligation vertices + HAS_OBLIGATION edges ─────────────────────────
    obligations = canonical.get("obligations", [])
    if isinstance(obligations, list):
        for i, ob in enumerate(obligations):
            ob_id  = f"{job_id}_ob_{i}"
            ob_desc = ob.get("description", ob) if isinstance(ob, dict) else str(ob)
            due     = ob.get("dueDate", "")    if isinstance(ob, dict) else ""
            upsert_vertex("Obligation", ob_id, {
                "description": str(ob_desc)[:250],
                "dueDate":     str(due),
                "index":       str(i),
            })
            upsert_edge(job_id, ob_id, "HAS_OBLIGATION")

    # ── 4. Deliverable vertices + HAS_DELIVERABLE edges ───────────────────────
    scope        = canonical.get("scope", {})
    deliverables = scope.get("deliverables", [])
    if isinstance(deliverables, list):
        for i, d in enumerate(deliverables):
            d_id   = f"{job_id}_del_{i}"
            d_name = d.get("name", d) if isinstance(d, dict) else str(d)
            d_due  = d.get("dueDate", "") if isinstance(d, dict) else ""
            upsert_vertex("Deliverable", d_id, {
                "name":    str(d_name)[:250],
                "dueDate": str(d_due),
                "index":   str(i),
            })
            upsert_edge(job_id, d_id, "HAS_DELIVERABLE")

    # ── 5. Milestone vertices + HAS_MILESTONE edges ───────────────────────────
    commercials = canonical.get("commercials", {})
    milestones  = commercials.get("milestones", [])
    if isinstance(milestones, list):
        for i, m in enumerate(milestones):
            m_id   = f"{job_id}_ms_{i}"
            m_name = m.get("name", m) if isinstance(m, dict) else str(m)
            m_date = m.get("dueDate", "") if isinstance(m, dict) else ""
            m_val  = m.get("value", "")  if isinstance(m, dict) else ""
            upsert_vertex("Milestone", m_id, {
                "name":    str(m_name)[:250],
                "dueDate": str(m_date),
                "value":   str(m_val),
                "index":   str(i),
            })
            upsert_edge(job_id, m_id, "HAS_MILESTONE")

    log.info(f"[GraphBuilder] Graph build complete for job {job_id}")


# ── Query helpers (used by /graph/* API endpoints) ────────────────────────────

def get_contract_parties(job_id: str) -> list:
    """Return all Party vertices linked to a contract."""
    return run_gremlin_query(
        f"g.V().has('Contract', 'entityId', '{_safe(job_id)}')"
        f".out('HAS_PARTY').valueMap(true)"
    )


def get_contract_obligations(job_id: str) -> list:
    """Return all Obligation vertices linked to a contract."""
    return run_gremlin_query(
        f"g.V().has('Contract', 'entityId', '{_safe(job_id)}')"
        f".out('HAS_OBLIGATION').valueMap(true)"
    )


def get_contract_deliverables(job_id: str) -> list:
    """Return all Deliverable vertices linked to a contract."""
    return run_gremlin_query(
        f"g.V().has('Contract', 'entityId', '{_safe(job_id)}')"
        f".out('HAS_DELIVERABLE').valueMap(true)"
    )


def get_contracts_by_party(party_name: str) -> list:
    """
    Cross-contract query: find all contracts that involve a named party.
    Useful for 'show me all contracts with Acme Corp'.
    """
    safe_name = _safe(party_name)
    return run_gremlin_query(
        f"g.V().hasLabel('Party').has('name', '{safe_name}')"
        f".in('HAS_PARTY').valueMap(true)"
    )


def get_full_graph(job_id: str) -> dict:
    """
    Return all vertices and edges for a contract as a dict.
    Used by the frontend graph visualiser.
    """
    vertices = run_gremlin_query(
        f"g.V().has('entityId', '{_safe(job_id)}')"
        f".union(__.identity(), __.out()).valueMap(true)"
    )
    edges = run_gremlin_query(
        f"g.V().has('entityId', '{_safe(job_id)}')"
        f".outE().project('label','from','to').by(label()).by(outV().values('entityId')).by(inV().values('entityId'))"
    )
    return {"vertices": vertices, "edges": edges}