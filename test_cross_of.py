import json
import re

with open("muv_menu_latest.json") as f:
    data = json.load(f)

products = data["products"]["list"]

print("Products with 'cross of ... and ...' pattern:\n")
pattern = r"cross of\s+([A-Za-z0-9#\s&']+?)\s+and\s+([A-Za-z0-9#\s&']+?)\."

for p in products:
    desc = p.get("description", "")
    match = re.search(pattern, desc, re.IGNORECASE)
    if match and "lineage:" not in desc.lower():
        name = p.get("name", "N/A")
        print(f"{name}: {match.group(0)}")
