"""Backfill Flowery genetics from Azure blob storage"""
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

print(" Finding Flowery menu files...")
blobs = list(container.list_blobs(name_starts_with="menus/flowery/"))
print(f"Found {len(blobs)} Flowery menu files\n")

genetics_data = {}
processed = 0

for blob in blobs[:100]:
    try:
        blob_client = container.get_blob_client(blob.name)
        content = blob_client.download_blob().readall()
        data = json.loads(content)
        
        # Extract - handle both direct and nested structures
        if "data" in data:
            data = data["data"]
        
        file_genetics = scraper._extract_flowery(data, blob.name)
        for g in file_genetics:
            genetics_data[g.strain_name] = (g.parent_1, g.parent_2)
        
        processed += 1
        if processed % 20 == 0:
            print(f"  Processed {processed}/{min(100, len(blobs))} files... ({len(genetics_data)} strains found)")
            
    except Exception as e:
        continue

print(f"\n=== BACKFILL COMPLETE ===\n")
print(f"Total unique strains: {len(genetics_data)}")

if genetics_data:
    print(f"\nSample strains:")
    for i, (strain, parents) in enumerate(list(genetics_data.items())[:15]):
        print(f"  {strain:35} {parents[0]} x {parents[1]}")

print(f"\n=== SUMMARY ===")
print(f"Files processed: {processed}")
print(f"Unique strains: {len(genetics_data)}")
if processed > 0:
    print(f"Coverage: {len(genetics_data) / processed * 100:.1f} strains per 100 files")
