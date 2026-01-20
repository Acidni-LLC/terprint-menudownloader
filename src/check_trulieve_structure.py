"""Check structure of one Trulieve blob"""
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")

# Get first Trulieve blob
blobs = list(container.list_blobs(name_starts_with="menus/trulieve/"))
first_blob = blobs[10] if len(blobs) > 10 else blobs[0]

print(f"Checking blob: {first_blob.name}\n")

blob_client = container.get_blob_client(first_blob.name)
content = blob_client.download_blob().readall()
data = json.loads(content)

print(f"Root keys: {list(data.keys())}\n")

if "products" in data:
    products = data["products"]
    print(f"Products (direct): {len(products)} items")
    if products and len(products) > 0:
        print(f"First product keys: {list(products[0].keys())}")
        if "custom_attributes_product" in products[0]:
            print(f"\nFirst product custom_attributes:")
            for attr in products[0]["custom_attributes_product"][:5]:
                print(f"  {attr.get(\"code\")}: {str(attr.get(\"value\"))[:50]}")

if "data" in data:
    nested_data = data["data"]
    print(f"\nData field keys: {list(nested_data.keys())}")
    if "products" in nested_data:
        products = nested_data["products"]
        print(f"Products (nested): {len(products)} items")
        if products and len(products) > 0:
            print(f"First product keys: {list(products[0].keys())}")
