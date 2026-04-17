"""
cosmos_client.py
─────────────────
Azure Cosmos DB SQL API client factory.
Used for persistent job storage (replaces in-memory JOBS dict).

Required env vars:
    AZURE_COSMOS_ENDPOINT   Cosmos DB account endpoint URL
    AZURE_COSMOS_KEY        Cosmos DB primary key
    COSMOS_DATABASE         Database name (default: contract-intelligence)
    COSMOS_CONTAINER        Container name  (default: jobs)
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
def get_cosmos_client():
    """
    Return a cached CosmosClient instance.
    pip install azure-cosmos
    """
    from azure.cosmos import CosmosClient
    endpoint = _require_env("AZURE_COSMOS_ENDPOINT")
    key      = _require_env("AZURE_COSMOS_KEY")
    log.info("[CosmosDB] Creating CosmosClient")
    return CosmosClient(url=endpoint, credential=key)


@lru_cache(maxsize=1)
def get_jobs_container():
    """
    Return (and auto-create if needed) the Cosmos DB container for job records.
    Partition key: /job_id
    """
    from azure.cosmos import PartitionKey

    client = get_cosmos_client()
    db_name        = os.getenv("COSMOS_DATABASE",  "contract-intelligence")
    container_name = os.getenv("COSMOS_CONTAINER", "jobs")

    database = client.create_database_if_not_exists(id=db_name)
    container = database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/job_id"),
        offer_throughput=400,       # Minimum RU/s — raise in production
    )
    log.info(f"[CosmosDB] Using container '{container_name}' in database '{db_name}'")
    return container