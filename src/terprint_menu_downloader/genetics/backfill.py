"""
Genetics backfill from historical menu blobs.

Usage:
  python -m terprint_menu_downloader.genetics.backfill \
    --dispensary trulieve \
    --max 200 \
    --save

Environment (optional):
  MENUS_STORAGE_ACCOUNT   default: stterprintsharedgen2
  MENUS_CONTAINER         default: jsonfiles
  AZURE_STORAGE_CONNECTION_STRING (preferred if available)
"""

import argparse
import json
import os
from typing import List, Tuple

from .scraper import GeneticsScraper
from .storage import GeneticsStorage

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.credentials import AzureNamedKeyCredential
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError:  # pragma: no cover - handled at runtime
    AZURE_AVAILABLE = False


def _connect_blob(account_name: str, container: str, conn_str: str, account_key: str, sas_token: str):
    if not AZURE_AVAILABLE:
        raise RuntimeError("azure-storage-blob is not installed. Install it to run backfill.")

    # Prefer connection string when provided (works for local dev and CI)
    if conn_str:
        print("[AUTH] Using storage connection string")
        svc = BlobServiceClient.from_connection_string(conn_str)
    elif account_key:
        print("[AUTH] Using account key credential")
        url = f"https://{account_name}.blob.core.windows.net"
        cred = AzureNamedKeyCredential(account_name, account_key)
        svc = BlobServiceClient(account_url=url, credential=cred)
    elif sas_token:
        print("[AUTH] Using SAS token")
        # SAS token may or may not include leading '?'
        sas = sas_token if sas_token.startswith("?") else f"?{sas_token}"
        url = f"https://{account_name}.blob.core.windows.net{sas}"
        svc = BlobServiceClient(account_url=url)
    else:
        print("[AUTH] Using DefaultAzureCredential (managed identity / Azure CLI)")
        url = f"https://{account_name}.blob.core.windows.net"
        cred = DefaultAzureCredential()
        svc = BlobServiceClient(account_url=url, credential=cred)
    return svc.get_container_client(container)


def _list_blobs(container_client, prefix: str, max_items: int) -> List[str]:
    blobs = []
    for blob in container_client.list_blobs(name_starts_with=prefix):
        name = getattr(blob, "name", "")
        if name.endswith(".json"):
            blobs.append(name)
        if len(blobs) >= max_items:
            break
    return blobs


def _download_json(container_client, name: str):
    data = container_client.download_blob(name).readall()
    return json.loads(data)


def run_backfill(dispensary: str, max_items: int, save: bool, prefix: str = None, enable_scraping: bool = False):
    account = os.environ.get("MENUS_STORAGE_ACCOUNT", "stterprintsharedgen2")
    container = os.environ.get("MENUS_CONTAINER", "jsonfiles")
    conn_str = (
        os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        or os.environ.get("STORAGE_ACCOUNT_CONNECTION_STRING")
        or os.environ.get("MENUS_STORAGE_CONNECTION_STRING")
    )
    account_key = (
        os.environ.get("MENUS_STORAGE_KEY")
        or os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
        or os.environ.get("AZURE_STORAGE_KEY")
    )
    sas_token = os.environ.get("MENUS_STORAGE_SAS") or os.environ.get("AZURE_STORAGE_SAS_TOKEN")

    container_client = _connect_blob(account, container, conn_str, account_key, sas_token)
    # Use default prefix when not provided
    search_prefix = prefix or f"dispensaries/{dispensary}/"

    print(f"[INFO] Listing blobs from {account}/{container} prefix={search_prefix} (max {max_items})")
    blob_names = _list_blobs(container_client, search_prefix, max_items)
    print(f"[INFO] Found {len(blob_names)} blob(s) to process")

    scraper = GeneticsScraper(enable_page_scraping=enable_scraping)
    all_genetics = []
    total_products = 0

    for name in blob_names:
        try:
            payload = _download_json(container_client, name)
            result = scraper.extract_from_menu(payload, dispensary=dispensary, source_file=name)
            all_genetics.extend(result.genetics_found)
            total_products += result.products_with_genetics
            print(f"[OK] {name}: strains={result.unique_strains}, products={result.products_with_genetics}")
        except Exception as exc:  # pragma: no cover - runtime logging
            print(f"[WARN] {name}: {exc}")

    print(f"\n[SUMMARY] blobs={len(blob_names)}, products_with_genetics={total_products}, strains={len(all_genetics)}")

    if save and all_genetics:
        print("[INFO] Saving genetics and refreshing index…")
        import asyncio

        async def _save_and_refresh():
            storage = GeneticsStorage()
            await storage.connect()
            await storage.save_genetics(all_genetics)
            await storage.refresh_index()

        try:
            asyncio.run(_save_and_refresh())
        except RuntimeError:
            import asyncio as aio
            loop = aio.new_event_loop()
            aio.set_event_loop(loop)
            loop.run_until_complete(_save_and_refresh())
            loop.close()
        print("[INFO] Genetics saved and index refreshed")
    elif save:
        print("[INFO] No genetics extracted; skip save")


def main():
    parser = argparse.ArgumentParser(description="Backfill genetics from historical menu blobs")
    parser.add_argument("--dispensary", required=True, help="Dispensary id (e.g., trulieve, cookies, curaleaf, muv, flowery, sunburn)")
    parser.add_argument("--max", dest="max_items", type=int, default=200, help="Max number of blobs to process")
    parser.add_argument("--prefix", help="Custom blob prefix override (default dispensaries/<dispensary>/)")
    parser.add_argument("--save", action="store_true", help="Persist genetics and refresh index")
    args = parser.parse_args()

    run_backfill(args.dispensary, args.max_items, args.save, args.prefix)


if __name__ == "__main__":
    raise SystemExit(main())