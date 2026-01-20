import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Download partition L
blob = client.get_blob_client("genetics-data", "partitions/l.json")
partition = json.loads(blob.download_blob().readall())

print(f"=== Partition L ===")
print(f"Total strains: {partition['strain_count']}")
print(f"Updated: {partition['updated_at']}\n")

print("Strains with parent genetics:\n")
for strain in partition["strains"]:
    if strain.get("parent_1"):
        print(f"{strain['strain_name']}:")
        print(f"  Parents: {strain['parent_1']} x {strain.get('parent_2', 'Unknown')}")
        print(f"  Type: {strain.get('strain_type', 'Unknown')}")
        print(f"  Dispensary: {strain.get('source_dispensary', 'Unknown')}")
        print()

# Check total across all partitions
blob = client.get_blob_client("genetics-data", "index/strains-index.json")
index = json.loads(blob.download_blob().readall())
print(f"\n=== Overall Summary ===")
print(f"Total strains indexed: {index['total_strains']}")
print(f"All have lineage data: {all(s.get('has_lineage') for s in index['strains'].values())}")
