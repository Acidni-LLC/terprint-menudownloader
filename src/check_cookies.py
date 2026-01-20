from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
import json
from datetime import datetime, timezone, timedelta

credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")

blobs = [b for b in container.list_blobs(name_starts_with="dispensaries/cookies/2026/01/") 
         if b.last_modified >= datetime.now(timezone.utc) - timedelta(days=3)]

recent = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[0]
blob_client = container.get_blob_client(recent.name)
data = json.loads(blob_client.download_blob().readall())

products = data.get("products", {})
print(f"Products keys: {products.keys()}")

if 'results' in products:
    results = products['results']
    print(f"\nResults count: {len(results)}")
    if results:
        prod = results[0]
        print(f"\nProduct fields: {list(prod.keys())}")
        print(f"\nName: {prod.get('name', 'N/A')}")
        
        # Show URL-related fields
        for key in sorted(prod.keys()):
            if 'url' in key.lower() or 'link' in key.lower() or 'slug' in key.lower() or 'path' in key.lower():
                value = str(prod[key])[:100]
                print(f"  {key}: {value}")
