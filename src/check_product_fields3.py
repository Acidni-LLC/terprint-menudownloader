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
    
    # Handle dict with 'list' key (MUV style)
    if isinstance(products, dict):
        if 'list' in products:
            products = products['list']
            print(f"Extracted products['list'], now type: {type(products)}, count: {len(products)}")
        else:
            print(f"Products dict keys: {list(products.keys())}")
            continue
    
    if not products:
        print("No products found")
        continue
        
    prod = products[0]
    print(f"\nProduct fields ({len(list(prod.keys()))} total): {list(prod.keys())}")
    print(f"\nName: {prod.get('name', 'N/A')}")
    
    # Show all URL-related fields
    print("\nURL-related fields:")
    for key in sorted(prod.keys()):
        if 'url' in key.lower() or 'link' in key.lower() or 'slug' in key.lower() or 'path' in key.lower():
            value = str(prod[key])[:100]
            print(f"  {key}: {value}")
