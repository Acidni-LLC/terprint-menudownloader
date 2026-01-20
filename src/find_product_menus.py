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

dispensaries = ["curaleaf", "muv", "cookies", "flowery"]
cutoff = datetime.now(timezone.utc) - timedelta(days=3)

for disp in dispensaries:
    print(f"\n{'='*60}")
    print(f"Checking {disp.upper()}")
    print('='*60)
    
    blobs = [b for b in container.list_blobs(name_starts_with=f"dispensaries/{disp}/2026/01/") 
             if b.last_modified >= cutoff]
    
    if not blobs:
        print(f"  No recent files found")
        continue
        
    recent = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[0]
    print(f"  File: {recent.name}")
    print(f"  Date: {recent.last_modified}")
    
    blob_client = container.get_blob_client(recent.name)
    data = json.loads(blob_client.download_blob().readall())
    
    print(f"  Keys: {list(data.keys())[:10]}")
    
    # Try to find product structure
    if "data" in data:
        print(f"  data keys: {list(data['data'].keys())[:10] if isinstance(data['data'], dict) else type(data['data'])}")
        if isinstance(data["data"], dict) and "products" in data["data"]:
            products = data["data"]["products"]
            if isinstance(products, dict) and "list" in products:
                products = products["list"]
            print(f"  Products found: {len(products) if isinstance(products, list) else 'not a list'}")
            if isinstance(products, list) and products:
                prod = products[0]
                print(f"  Sample product: {json.dumps(prod, indent=4)[:400]}")
