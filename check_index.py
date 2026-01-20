import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Download index
blob = client.get_blob_client("genetics-data", "index/strains-index.json")
index = json.loads(blob.download_blob().readall())

print("Index structure:")
print(json.dumps(index, indent=2)[:2000])
