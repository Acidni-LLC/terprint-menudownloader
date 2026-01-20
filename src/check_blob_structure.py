from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(account_url="https://stterprintsharedgen2.blob.core.windows.net", credential=credential)
container = blob_service.get_container_client("jsonfiles")

blob_name = "menus/muv/367_20251201_033210.json"
blob_client = container.get_blob_client(blob_name)
data = json.loads(blob_client.download_blob().readall())

print(f"Root structure:")
print(f"  dispensary: {data.get('dispensary')}")
print(f"  store_id: {data.get('store_id')}")
print(f"  timestamp: {data.get('timestamp')}")

# Check data field
menu_data = data.get("data", {})
print(f"\nData field type: {type(menu_data)}")
print(f"Data field keys: {list(menu_data.keys()) if isinstance(menu_data, dict) else 'N/A'}")

# Check if products is nested in data
if "products" in menu_data:
    products = menu_data["products"]
    print(f"\nProducts type: {type(products)}")
    if isinstance(products, dict):
        print(f"Products keys: {list(products.keys())}")
        if "list" in products:
            print(f"Products.list length: {len(products['list'])}")
            if len(products["list"]) > 0:
                first = products["list"][0]
                print(f"\nFirst product keys: {list(first.keys())}")
                # Check for lineage
                desc = first.get("description", "")
                if "lineage" in desc.lower():
                    print(f"\nLineage found in first product:")
                    idx = desc.lower().index("lineage")
                    print(desc[idx:idx+100])
