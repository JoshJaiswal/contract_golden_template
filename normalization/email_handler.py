"""
email_handler.py
────────────────
Handles email message files (.eml/.msg). This stub provides a valid
handler function for pipeline import and placeholder output.
"""

import logging
from typing import Literal

log = logging.getLogger(__name__)


def handle_email(
    file_path: str,
    contract_type: Literal["nda", "sow", "auto"] = "auto",
    upload_to_blob: bool = True,
) -> list[dict]:
    """Process an email file and return extraction results."""
    log.warning("[Email Handler] Email extraction is not implemented yet. Returning stub empty output.")
    return [{
        "_source": "email_stub",
        "contractType": contract_type,
        "_confidence": 0.0,
    }]
    """
    Upload a file to Azure Blob Storage and return a time-limited SAS URL.

    Args:
        file_path:  Local path to the file to upload.
        container:  Blob container name (will be created if it doesn't exist).

    Returns:
        SAS URL string that grants read access for SAS_EXPIRY_HOURS.
    """
    from config.azure_clients import get_blob_client
    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    path = Path(file_path)
    blob_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{path.name}"

    client = get_blob_client()

    # Ensure container exists
    container_client = client.get_container_client(container)
    if not container_client.exists():
        container_client.create_container()
        log.info(f"[Blob] Created container: {container}")

    # Upload the file
    blob_client = client.get_blob_client(container=container, blob=blob_name)
    with open(file_path, "rb") as f:
        blob_client.upload_blob(f, overwrite=True)
    log.info(f"[Blob] Uploaded: {blob_name} → {container}")

    # Generate SAS URL
    # TODO: Replace account_name and account_key with values from your connection string
    account_name = _get_account_name()
    account_key = _get_account_key()

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=SAS_EXPIRY_HOURS),
    )

    sas_url = f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}?{sas_token}"
    return sas_url


def _get_account_name() -> str:
    """Extract storage account name from connection string or env var."""
    conn_str = os.getenv("AZURE_BLOB_CONNECTION_STR", "")
    for part in conn_str.split(";"):
        if part.startswith("AccountName="):
            return part.split("=", 1)[1]
    raise EnvironmentError("Could not extract AccountName from AZURE_BLOB_CONNECTION_STR")


def _get_account_key() -> str:
    """Extract storage account key from connection string."""
    conn_str = os.getenv("AZURE_BLOB_CONNECTION_STR", "")
    for part in conn_str.split(";"):
        if part.startswith("AccountKey="):
            return part.split("=", 1)[1]
    raise EnvironmentError("Could not extract AccountKey from AZURE_BLOB_CONNECTION_STR")