"""Backfill Trulieve genetics from Azure blob storage"""
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
from terprint_menu_downloader.genetics.scraper import GeneticsScraper
import json

# Initialize
credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")
scraper = GeneticsScraper()

# Find Trulieve blobs
print(" Finding Trulieve menu files...")
blobs = list(container.list_blobs(name_starts_with="menus/trulieve/"))
print(f"Found {len(blobs)} Trulieve menu files\n")

# Process blobs
genetics_data = {}
processed = 0

for blob in blobs[:100]:  # Process first 100 files
    try:
        blob_client = container.get_blob_client(blob.name)
        content = blob_client.download_blob().readall()
        data = json.loads(content)
        
        # Extract genetics from this blob
        file_genetics = scraper._extract_trulieve(data)
        genetics_data.update(file_genetics)
        
        processed += 1
        if processed % 20 == 0:
            print(f"  Processed {processed}/{min(100, len(blobs))} files... ({len(genetics_data)} strains found)")
            
    except Exception as e:
        continue

print(f"\n=== BACKFILL COMPLETE ===\n")
print(f"Total unique strains with genetics: {len(genetics_data)}")
print(f"Total strain-parent associations: {sum(len(v) for v in genetics_data.values())}")

if genetics_data:
    print(f"\nAll {len(genetics_data)} strains found:")
    for strain, parents in sorted(genetics_data.items()):
        if len(parents) == 2:
            print(f"  {strain:35} {parents[0]} x {parents[1]}")
        else:
            print(f"  {strain:35} {' x '.join(parents)}")

print(f"\n=== SUMMARY ===")
print(f"Files processed: {processed}")
print(f"Unique strains: {len(genetics_data)}")
print(f"Coverage: {len(genetics_data) / processed * 100:.1f} strains per 100 files")
