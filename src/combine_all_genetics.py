"""Combine all genetics extractions and save results"""
from azure.storage.blob import BlobServiceClient
from azure.identity import AzureCliCredential
from terprint_menu_downloader.genetics.scraper import GeneticsScraper
from datetime import datetime
import json

credential = AzureCliCredential()
blob_service = BlobServiceClient(
    account_url="https://stterprintsharedgen2.blob.core.windows.net",
    credential=credential
)
container = blob_service.get_container_client("jsonfiles")
scraper = GeneticsScraper()

# Collect all genetics
all_genetics = {}
dispensary_counts = {}

# MÜV (already extracted)
print("Processing MÜV...")
muv_blobs = list(container.list_blobs(name_starts_with="menus/muv/"))
for blob in muv_blobs:
    try:
        data = json.loads(container.get_blob_client(blob.name).download_blob().readall())
        menu_data = data.get("data", data)
        for g in scraper._extract_muv(menu_data, blob.name):
            all_genetics[g.strain_name] = {
                "dispensary": "muv",
                "parent1": g.parent_1,
                "parent2": g.parent_2,
                "strain_type": g.strain_type
            }
    except:
        continue
dispensary_counts["muv"] = len([g for g in all_genetics.values() if g["dispensary"] == "muv"])
print(f" MÜV: {dispensary_counts['muv']} strains")

# Cookies
print("Processing Cookies...")
cookies_blobs = list(container.list_blobs(name_starts_with="menus/cookies/"))
for blob in cookies_blobs:
    try:
        data = json.loads(container.get_blob_client(blob.name).download_blob().readall())
        menu_data = data.get("data", data)
        for g in scraper._extract_cookies(menu_data, blob.name):
            if g.strain_name not in all_genetics:
                all_genetics[g.strain_name] = {
                    "dispensary": "cookies",
                    "parent1": g.parent_1,
                    "parent2": g.parent_2,
                    "strain_type": g.strain_type
                }
    except:
        continue
dispensary_counts["cookies"] = len([g for g in all_genetics.values() if g["dispensary"] == "cookies"])
print(f" Cookies: {dispensary_counts['cookies']} strains")

# Save results
output = {
    "extraction_date": datetime.now().isoformat(),
    "total_strains": len(all_genetics),
    "by_dispensary": dispensary_counts,
    "strains": [
        {
            "strain_name": name,
            "parent1": data["parent1"],
            "parent2": data["parent2"],
            "dispensary": data["dispensary"],
            "strain_type": data.get("strain_type")
        }
        for name, data in sorted(all_genetics.items())
    ]
}

filename = f"all_genetics_{datetime.now().strftime('%Y%m%d')}.json"
with open(filename, "w") as f:
    json.dump(output, f, indent=2)

print(f"\n{'=' * 60}")
print("FINAL RESULTS")
print(f"{'=' * 60}")
print(f"Total unique strains: {len(all_genetics)}")
print(f"\nBy dispensary:")
for disp, count in sorted(dispensary_counts.items()):
    print(f"  {disp.upper():12} {count} strains")
print(f"\n Saved to {filename}")
print(f"\nSample strains (first 20):")
for i, (name, data) in enumerate(list(all_genetics.items())[:20]):
    print(f"  {name:35} {data['parent1']} x {data['parent2']} ({data['dispensary']})")
