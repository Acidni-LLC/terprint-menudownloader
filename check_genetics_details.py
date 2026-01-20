import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Check partition L (should have Lemon Cherry Gelato)
blob = client.get_blob_client("genetics-data", "partitions/l.json")
partition_data = json.loads(blob.download_blob().readall())

print("Strains in partition L with parent genetics:\n")
for strain_id, genetics in partition_data.items():
    lineage = genetics.get("lineage", {})
    if lineage.get("parent_1"):
        parent1 = lineage["parent_1"]
        parent2 = lineage.get("parent_2", "Unknown")
        dispensaries = ", ".join(genetics.get("found_at_dispensaries", []))
        print(f"{genetics.get('name', strain_id)}:")
        print(f"  Parents: {parent1} x {parent2}")
        print(f"  Found at: {dispensaries}")
        print()
