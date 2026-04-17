"""
gremlin_client.py
──────────────────
Azure Cosmos DB Gremlin API client factory.
Used for the knowledge graph (entity + relationship storage).

Required env vars:
    COSMOS_GREMLIN_ENDPOINT   wss://<account>.gremlin.cosmos.azure.com:443/
    COSMOS_GREMLIN_KEY        Cosmos DB primary key
    COSMOS_GREMLIN_DATABASE   Gremlin database name  (default: contract-graph)
    COSMOS_GREMLIN_GRAPH      Gremlin graph name     (default: entities)
"""

import os
import logging
from functools import lru_cache

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

log = logging.getLogger(__name__)


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Missing required environment variable: {key}\n"
            f"Add it to your .env file. See .env.example for all required vars."
        )
    return val


@lru_cache(maxsize=1)
def get_gremlin_client():
    """
    Return a cached Gremlin Client connected to Cosmos DB.
    pip install gremlinpython
    """
    from gremlin_python.driver import client as gremlin_client_mod, serializer

    endpoint = _require_env("COSMOS_GREMLIN_ENDPOINT")
    key      = _require_env("COSMOS_GREMLIN_KEY")
    database = os.getenv("COSMOS_GREMLIN_DATABASE", "contract-graph")
    graph    = os.getenv("COSMOS_GREMLIN_GRAPH",    "entities")

    username = f"/dbs/{database}/colls/{graph}"

    log.info(f"[Gremlin] Connecting to {endpoint} → {username}")

    gremlin = gremlin_client_mod.Client(
        url=endpoint,
        traversal_source="g",
        username=username,
        password=key,
        message_serializer=serializer.GraphSONSerializersV2d0(),
    )
    return gremlin


def run_gremlin_query(query: str) -> list:
    """
    Execute a Gremlin query and return all results.
    Handles connection errors gracefully.
    """
    try:
        g = get_gremlin_client()
        return g.submit(query).all().result()
    except Exception as e:
        log.error(f"[Gremlin] Query failed: {e}\nQuery: {query}")
        raise