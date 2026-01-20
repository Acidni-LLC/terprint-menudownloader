from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")

# Get recent Trulieve menu
blobs = list(container.list_blobs(name_starts_with="dispensaries/trulieve/2026/01/"))
if blobs:
    recent = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[0]
    blob_client = container.get_blob_client(recent.name)
    data = json.loads(blob_client.download_blob().readall())
    
    print(f"Found {recent.name}")
    print(f"Menu keys: {list(data.keys())}")
    
    # Find products
    if "categories" in data:
        for cat in data["categories"][:2]:
            if "products" in cat:
                print(f"\nCategory: {cat.get('name', 'Unknown')}")
                print(f"Products found: {len(cat['products'])}")
                if cat["products"]:
                    prod = cat["products"][0]
                    print(f"Product keys: {list(prod.keys())}")
                    print(f"Name: {prod.get('name', 'N/A')}")
                    print(f"Slug: {prod.get('slug', 'N/A')}")
                    print(f"URL: {prod.get('url', 'N/A')}")
                break
