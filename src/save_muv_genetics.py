"""Save MÜV genetics data to Azure Storage"""
from terprint_menu_downloader.genetics.scraper import GeneticsScraper
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
from datetime import datetime
import json

# Run extraction
scraper = GeneticsScraper()
print(" Extracting MÜV genetics data...")
genetics_data = scraper.extract_from_dispensary("muv", days_back=90)

# Prepare output
output = {
    "dispensary": "muv",
    "extraction_date": datetime.now().isoformat(),
    "total_strains": len(genetics_data),
    "strains": [
        {
            "strain_name": strain,
            "parent1": parents[0],
            "parent2": parents[1]
        }
        for strain, parents in genetics_data.items()
    ]
}

# Save locally
filename = f"muv_genetics_{datetime.now().strftime('%Y%m%d')}.json"
with open(filename, "w") as f:
    json.dump(output, f, indent=2)
print(f" Saved to {filename}")

# Upload to Azure
try:
    credential = AzureCliCredential()
    blob_service = BlobServiceClient(
        account_url="https://stterprintsharedgen2.blob.core.windows.net",
        credential=credential
    )
    container = blob_service.get_container_client("jsonfiles")
    
    blob_name = f"genetics/muv/{filename}"
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(json.dumps(output, indent=2), overwrite=True)
    print(f" Uploaded to Azure: {blob_name}")
except Exception as e:
    print(f" Azure upload failed: {e}")
    print("Local file saved successfully")
