import json
from azure.storage.blob import BlobServiceClient
import os

connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
blob_service = BlobServiceClient.from_connection_string(connection_string)
container = blob_service.get_container_client("jsonfiles")

dispensaries = ["cookies", "flowery", "curaleaf"]

for disp in dispensaries:
    print(f"\n=== {disp.upper()} ===")
    
    prefix = f"dispensaries/{disp}/2026/01/"
    blobs = list(container.list_blobs(name_starts_with=prefix))
    
    if blobs:
        latest = sorted(blobs, key=lambda b: b.name, reverse=True)[0]
        print(f"Latest: {latest.name}")
        
        blob_client = container.get_blob_client(latest.name)
        data = json.loads(blob_client.download_blob().readall())
        
        # Save full menu
        filename = f"{disp}_menu_latest.json"
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved: {filename}")
        
        # Show structure
        print(f"Keys: {list(data.keys())[:10]}")
        
        # Try to find products
        if isinstance(data, dict):
            for key in ["products", "menu", "data", "items"]:
                if key in data:
                    products = data[key]
                    if products and len(products) > 0:
                        print(f"Found {len(products)} products in '{key}'")
                        # Save first product
                        with open(f"{disp}_product_sample.json", "w") as f:
                            json.dump(products[0], f, indent=2)
                        print(f"Sample: {products[0].get('name', products[0].get('product_name', 'N/A'))}")
                        break
        elif isinstance(data, list):
            print(f"Data is a list with {len(data)} items")
            if data:
                with open(f"{disp}_product_sample.json", "w") as f:
                    json.dump(data[0], f, indent=2)
