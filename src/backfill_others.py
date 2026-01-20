"""Backfill genetics from Cookies and Curaleaf"""
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
from terprint_menu_downloader.genetics.scraper import GeneticsScraper
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")
scraper = GeneticsScraper()

# Process Cookies
print("=" * 60)
print("COOKIES BACKFILL")
print("=" * 60)
blobs = list(container.list_blobs(name_starts_with="menus/cookies/"))
print(f"Found {len(blobs)} Cookies files")

cookies_data = {}
for blob in blobs[:50]:
    try:
        blob_client = container.get_blob_client(blob.name)
        data = json.loads(blob_client.download_blob().readall())
        if "data" in data:
            data = data["data"]
        file_genetics = scraper._extract_cookies(data, blob.name)
        for g in file_genetics:
            cookies_data[g.strain_name] = (g.parent_1, g.parent_2)
    except:
        continue

print(f"Extracted {len(cookies_data)} Cookies strains\n")

# Process Curaleaf
print("=" * 60)
print("CURALEAF BACKFILL")
print("=" * 60)
blobs = list(container.list_blobs(name_starts_with="menus/curaleaf/"))
print(f"Found {len(blobs)} Curaleaf files")

curaleaf_data = {}
for blob in blobs[:50]:
    try:
        blob_client = container.get_blob_client(blob.name)
        data = json.loads(blob_client.download_blob().readall())
        if "data" in data:
            data = data["data"]
        file_genetics = scraper._extract_curaleaf(data, blob.name)
        for g in file_genetics:
            curaleaf_data[g.strain_name] = (g.parent_1, g.parent_2)
    except:
        continue

print(f"Extracted {len(curaleaf_data)} Curaleaf strains\n")

# Summary
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Cookies:  {len(cookies_data)} strains")
print(f"Curaleaf: {len(curaleaf_data)} strains")
print(f"TOTAL:    {len(cookies_data) + len(curaleaf_data)} strains")

if cookies_data:
    print(f"\nCookies samples:")
    for strain, parents in list(cookies_data.items())[:5]:
        print(f"  {strain:30} {parents[0]} x {parents[1]}")

if curaleaf_data:
    print(f"\nCuraleaf samples:")
    for strain, parents in list(curaleaf_data.items())[:5]:
        print(f"  {strain:30} {parents[0]} x {parents[1]}")
