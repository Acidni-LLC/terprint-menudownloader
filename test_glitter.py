import json

with open("muv_menu_latest.json") as f:
    data = json.load(f)

products = data["products"]["list"]

for p in products:
    name = p.get("name", "").split(" - ")[0].strip()
    if "Glitter" in name:
        desc = p.get("description", "")
        if "lineage:" in desc.lower():
            idx = desc.lower().index("lineage:")
            print(f"{name} HAS Lineage field:")
            print(desc[idx:idx+100])
        else:
            print(f"{name} NO Lineage field")
            # Show the cross of text
            if "cross of" in desc.lower():
                idx = desc.lower().index("cross of")
                print(f"Has 'cross of': {desc[idx:idx+80]}")
