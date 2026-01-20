import sys
sys.path.insert(0, "src")

from terprint_menu_downloader.genetics.scraper import GeneticsScraper
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
import json
from collections import defaultdict
from datetime import datetime, timedelta

print("\n=== MÜV GENETICS BACKFILL ===\n")
print("Connecting to Azure Blob Storage via Azure CLI credentials...")

# Use AzureCliCredential for local dev (same as existing code)
credential = AzureCliCredential()
account_url = "https://stterprintsharedgen2.blob.core.windows.net"
blob_service = BlobServiceClient(account_url=account_url, credential=credential)
container = blob_service.get_container_client("jsonfiles")

# Calculate date range (last 3 months)
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

# Find MÜV blobs
print(f"Searching for MÜV menu files from {start_date.date()} to {end_date.date()}...")
muv_blobs = []
for blob in container.list_blobs(name_starts_with="menus/muv/"):
    if blob.name.endswith(".json"):
        muv_blobs.append(blob)
        if len(muv_blobs) >= 500:
            break

print(f"Found {len(muv_blobs)} MÜV menu files\n")

# Extract genetics
scraper = GeneticsScraper()
all_genetics = defaultdict(lambda: {"strains": set(), "associations": []})

print("Processing files...")
for i, blob in enumerate(muv_blobs, 1):
    if i % 50 == 0:
        print(f"  Processed {i}/{len(muv_blobs)} files...")
    
    try:
        blob_client = container.get_blob_client(blob.name)
        data = json.loads(blob_client.download_blob().readall())
        
        genetics = scraper._extract_muv(data, blob.name)
        
        for g in genetics:
            all_genetics[g.strain_name]["strains"].add(g.strain_name)
            # Store as tuple for uniqueness
            parent_tuple = (g.parent_1, g.parent_2)
            if parent_tuple not in all_genetics[g.strain_name]["associations"]:
                all_genetics[g.strain_name]["associations"].append(parent_tuple)
    except Exception as e:
        continue  # Skip errors

# Print results
total_associations = sum(len(v["associations"]) for v in all_genetics.values())

print(f"\n=== BACKFILL COMPLETE ===\n")
print(f"Total unique strains with genetics: {len(all_genetics)}")
print(f"Total strain-parent associations: {total_associations}")

print(f"\nAll {len(all_genetics)} strains found:")
for strain in sorted(all_genetics.keys()):
    parents = all_genetics[strain]["associations"][0]
    print(f"  {strain:35} {parents[0]} x {parents[1]}")

# Summary stats
print(f"\n=== SUMMARY ===")
print(f"Files processed: {len(muv_blobs)}")
print(f"Unique strains: {len(all_genetics)}")
print(f"Coverage: {len(all_genetics)/len(muv_blobs)*100:.1f} strains per 100 files")
