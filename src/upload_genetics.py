"""Upload genetics data to Azure Blob Storage"""
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
from datetime import datetime
import json

# Load the genetics data
with open("all_genetics_20260120.json", "r") as f:
    genetics_data = json.load(f)

print(f"Loaded {genetics_data['total_strains']} strains")

# Connect to Azure Storage
credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")

# Upload to genetics folder with timestamp
blob_name = f"genetics/combined/all_genetics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
blob_client = container.get_blob_client(blob_name)

print(f"Uploading to: {blob_name}")
blob_client.upload_blob(json.dumps(genetics_data, indent=2), overwrite=True)

print(f" Successfully uploaded to Azure Storage")
print(f"   Path: jsonfiles/{blob_name}")
print(f"   Strains: {genetics_data['total_strains']}")
print(f"   MÜV: {genetics_data['by_dispensary']['muv']}")
print(f"   Cookies: {genetics_data['by_dispensary']['cookies']}")
