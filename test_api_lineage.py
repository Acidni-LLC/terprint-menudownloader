import requests

# Query the recommender API for a strain we know has genetics
strain_name = "lemon-cherry-x-cap-junky"
api_url = f"https://apim-terprint-dev.azure-api.net/recommend/api/strains/{strain_name}"

# You would need the APIM subscription key here
# For now, let's just check the genetics storage directly since we don't have the key handy

from azure.storage.blob import BlobServiceClient
import json
import os

client = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=os.environ["AZURE_STORAGE_CONNECTION_STRING"].split(";")[2].split("=", 1)[1]
)

# Check partition L for Lemon Cherry x Cap Junky
blob = client.get_blob_client("genetics-data", "partitions/l.json")
partition = json.loads(blob.download_blob().readall())

lemon_cherry = next((s for s in partition["strains"] if s["strain_slug"] == strain_name), None)

if lemon_cherry:
    print(f" Found '{lemon_cherry['strain_name']}' in genetics storage!")
    print(f"  Parent 1: {lemon_cherry['parent_1']}")
    print(f"  Parent 2: {lemon_cherry.get('parent_2', 'N/A')}")
    print(f"  Strain Type: {lemon_cherry.get('strain_type', 'Unknown')}")
    print(f"  Source: {lemon_cherry.get('source_dispensary', 'Unknown')}")
    print(f"\nGenetics data is ready for the recommender API to use!")
else:
    print(f" Strain '{strain_name}' not found in genetics storage")
