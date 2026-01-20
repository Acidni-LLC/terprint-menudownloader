import json
import re

with open("muv_menu_latest.json") as f:
    data = json.load(f)

products = data["products"]["list"]

for p in products:
    name = p.get("name", "").split(" - ")[0].strip()
    if "Pineapple Wino" in name:
        desc = p.get("description", "")
        if "lineage:" in desc.lower():
            match = re.search(r"lineage:\s*([^\n]+)", desc, re.IGNORECASE)
            print(f"{name}:")
            print(f"  RAW lineage text: {match.group(1) if match else 'NOT FOUND'}")
