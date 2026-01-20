import json
from azure.storage.blob import BlobServiceClient
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Check Cookies menu structure
print("=== COOKIES Menu Structure ===")
blob = client.get_blob_client("jsonfiles", "sample_cookies_product.json")
cookies_data = json.loads(blob.download_blob().readall())
if isinstance(cookies_data, list) and len(cookies_data) > 0:
    sample = cookies_data[0]
    print(f"Sample product keys: {list(sample.keys())[:15]}")
    if "url" in sample or "link" in sample or "slug" in sample:
        print(f"URL field: {sample.get('url', sample.get('link', sample.get('slug')))}")
    print(f"\nFull sample product:\n{json.dumps(sample, indent=2)[:800]}")

print("\n" + "="*50 + "\n")

# Check Flowery menu structure  
print("=== FLOWERY Menu Structure ===")
blob = client.get_blob_client("jsonfiles", "sample_flowery.json")
flowery_data = json.loads(blob.download_blob().readall())
if "products" in flowery_data and len(flowery_data["products"]) > 0:
    sample = flowery_data["products"][0]
    print(f"Sample product keys: {list(sample.keys())}")
    if "url" in sample or "link" in sample or "slug" in sample or "id" in sample:
        print(f"\nURL/ID fields found:")
        for key in ["url", "link", "slug", "id", "product_id"]:
            if key in sample:
                print(f"  {key}: {sample[key]}")
    print(f"\nFull sample product:\n{json.dumps(sample, indent=2)[:800]}")
