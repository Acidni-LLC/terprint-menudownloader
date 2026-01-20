import json
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential
import os

# Get latest menu from blob storage for each dispensary
connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
if not connection_string:
    print("ERROR: AZURE_STORAGE_CONNECTION_STRING not set")
    exit(1)

blob_service = BlobServiceClient.from_connection_string(connection_string)
container = blob_service.get_container_client("jsonfiles")

dispensaries = ["cookies", "flowery", "curaleaf"]

for disp in dispensaries:
    print(f"\n=== {disp.upper()} - Finding latest menu ===")
    
    # List blobs for this dispensary
    prefix = f"dispensaries/{disp}/2026/01/"
    blobs = list(container.list_blobs(name_starts_with=prefix))
    
    if blobs:
        # Get most recent
        latest = sorted(blobs, key=lambda b: b.name, reverse=True)[0]
        print(f"Latest: {latest.name}")
        
        # Download and parse
        blob_client = container.get_blob_client(latest.name)
        data = json.loads(blob_client.download_blob().readall())
        
        # Find first flower product with a link/detail_url
        products = data.get("products", data.get("menu", []))
        for product in products[:50]:  # Check first 50
            # Check if flower category
            category = product.get("category", "").lower()
            if "flower" in category or product.get("product_type") == "flower":
                # Check if has URL
                url = product.get("link") or product.get("detail_url") or product.get("url")
                if url:
                    print(f"\nSample flower product:")
                    print(f"  Name: {product.get('name', product.get('product_name', 'N/A'))}")
                    print(f"  URL: {url}")
                    print(f"  Category: {category}")
                    
                    # Save sample product JSON
                    filename = f"{disp}_product_sample.json"
                    with open(filename, "w") as f:
                        json.dump(product, f, indent=2)
                    print(f"  Saved: {filename}")
                    break
