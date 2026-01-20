import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Download partition L
blob = client.get_blob_client("genetics-data", "partitions/l.json")
raw_data = blob.download_blob().readall().decode("utf-8")

print("First 2000 characters of partition L:")
print(raw_data[:2000])
