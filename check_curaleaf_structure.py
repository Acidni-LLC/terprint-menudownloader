import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Get a recent Curaleaf menu file
print("=== Searching for Curaleaf menu files ===")
container = client.get_container_client("jsonfiles")
curaleaf_blobs = [b for b in container.list_blobs(name_starts_with="dispensaries/curaleaf/2026/01/") if b.name.endswith(".json")]

if curaleaf_blobs:
    # Get the first one
    blob_name = curaleaf_blobs[0].name
    print(f"Loading: {blob_name}\n")
    
    blob_client = client.get_blob_client("jsonfiles", blob_name)
    menu_data = json.loads(blob_client.download_blob().readall())
    
    print(f"Menu structure type: {type(menu_data)}")
    if isinstance(menu_data, dict):
        print(f"Menu keys: {list(menu_data.keys())[:10]}")
    
    # Find products
    if isinstance(menu_data, dict) and "products" in menu_data:
        products = menu_data["products"]
    elif isinstance(menu_data, list):
        products = menu_data
    else:
        products = []
    
    if products and len(products) > 0:
        sample = products[0]
        print(f"\nSample product type: {type(sample)}")
        if isinstance(sample, dict):
            print(f"Sample product keys: {list(sample.keys())}")
            print(f"\nFull sample product:")
            print(json.dumps(sample, indent=2)[:1500])
            
            # Check for URL fields
            url_fields = ["url", "link", "slug", "id", "product_id", "href", "menuUrl"]
            found_urls = {k: sample.get(k) for k in url_fields if k in sample}
            if found_urls:
                print(f"\n URL/ID fields found: {found_urls}")
            else:
                print("\n No URL/ID fields found in product")
    else:
        print("No products found in menu")
else:
    print("No Curaleaf menu files found for January 2026")
