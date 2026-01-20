import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Check the strains index
blob = client.get_blob_client("genetics-data", "index/strains-index.json")
index = json.loads(blob.download_blob().readall())

print(f"Total strains in index: {len(index)}")
print("\nSample strains with parent genetics (first 15):")
count = 0
for strain_name, strain_data in sorted(index.items()):
    lineage = strain_data.get("lineage", {})
    if lineage.get("parent_1"):
        parent2 = lineage.get("parent_2", "Unknown")
        print(f"  {strain_name}: {lineage['parent_1']} x {parent2}")
        count += 1
        if count >= 15:
            break

# Count total with genetics
total_with_genetics = sum(1 for v in index.values() if v.get("lineage", {}).get("parent_1"))
print(f"\nTotal strains with parent genetics: {total_with_genetics} / {len(index)}")
