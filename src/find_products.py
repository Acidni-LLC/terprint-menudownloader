from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(account_url="https://stterprintsharedgen2.blob.core.windows.net", credential=credential)
container = blob_service.get_container_client("jsonfiles")

# Try to find a blob with products
print("Searching for MÜV blobs with products...\n")
found_count = 0
for blob in container.list_blobs(name_starts_with="menus/muv/"):
    if not blob.name.endswith(".json"):
        continue
    
    try:
        blob_client = container.get_blob_client(blob.name)
        data = json.loads(blob_client.download_blob().readall())
        
        # Check if it has products
        menu_data = data.get("data", {})
        products_list = menu_data.get("products", {}).get("list", [])
        
        if len(products_list) > 0:
            print(f"Found blob with {len(products_list)} products: {blob.name}")
            
            # Check for lineage in products
            lineage_count = 0
            for p in products_list:
                desc = p.get("description", "")
                if "lineage:" in desc.lower():
                    lineage_count += 1
            
            print(f"  Products with lineage: {lineage_count}")
            
            if lineage_count > 0:
                # Show sample
                for p in products_list:
                    desc = p.get("description", "")
                    if "lineage:" in desc.lower():
                        print(f"\n  Sample strain: {p.get('name', 'N/A')}")
                        idx = desc.lower().index("lineage:")
                        print(f"  {desc[idx:idx+80]}")
                        break
            
            found_count += 1
            if found_count >= 5:
                break
    except Exception as e:
        continue

print(f"\nTotal blobs checked: {found_count}")
