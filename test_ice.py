import json
import re

with open("muv_menu_latest.json") as f:
    data = json.load(f)

products = data["products"]["list"]

for p in products:
    name = p["name"].split(" - ")[0].strip()
    if name == "Ice Cream Candy":
        desc = p["description"]
        
        # Show relevant portion
        if "Dolato" in desc:
            idx = desc.index("Dolato")
            print(f"Text around Dolato:\n{desc[max(0,idx-50):idx+100]}\n")
        
        # Find all x patterns  
        all_x = re.findall(r"([A-Za-z0-9#\s]{5,25})\s*[xX]\s*([A-Za-z0-9#\s]{5,25})", desc)
        print(f"All 'x' patterns found:")
        for i, (p1, p2) in enumerate(all_x, 1):
            print(f"  {i}. {p1.strip()} x {p2.strip()}")
        break
