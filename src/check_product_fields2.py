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
    print(f"\n{'='*70}")
    print(f"{disp.upper()} - Product Structure")
    print('='*70)
    
    blobs = [b for b in container.list_blobs(name_starts_with=f"dispensaries/{disp}/2026/01/") 
             if b.last_modified >= cutoff]
    
    if not blobs:
        continue
        
    recent = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[0]
    blob_client = container.get_blob_client(recent.name)
    data = json.loads(blob_client.download_blob().readall())
    
    products = data.get("products", [])
    print(f"Products type: {type(products)}")
    
    if isinstance(products, dict):
        print(f"Products is a dict with keys: {list(products.keys())[:10]}")
        # Try to get first item
        if products:
            first_key = list(products.keys())[0]
            prod = products[first_key]
    elif isinstance(products, list) and products:
        prod = products[0]
    else:
        print(f"No products found or unexpected structure")
        continue
    
    print(f"\nProduct fields: {list(prod.keys())}")
    print(f"Name: {prod.get('name', 'N/A')}")
    print(f"Slug: {prod.get('slug', 'N/A')}")
    print(f"URL: {prod.get('url', 'N/A')}")
    
    # Show all URL-related fields
    for key in prod.keys():
        if 'url' in key.lower() or 'link' in key.lower() or 'slug' in key.lower():
            print(f"  {key}: {prod[key]}")
