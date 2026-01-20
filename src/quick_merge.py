import json

# Load both sources
with open("all_genetics_20260120.json", "r") as f:
    original = json.load(f)

with open("menu_description_genetics_20260120_045406.json", "r") as f:
    menu_desc = json.load(f)

orig_genetics = original.get("genetics", [])
desc_genetics = menu_desc.get("genetics", [])

print(f"Original: {len(orig_genetics)} genetics")
print(f"Menu descriptions: {len(desc_genetics)} genetics")

# Merge
all_genetics = {}
for g in orig_genetics:
    all_genetics[g["strain_name"]] = {
        "strain_name": g["strain_name"],
        "parent1": g.get("parent1", ""),
        "parent2": g.get("parent2", ""),
        "dispensary": g.get("dispensary", ""),
        "source": "Menu JSON"
    }

for g in desc_genetics:
    if g["strain_name"] not in all_genetics:
        all_genetics[g["strain_name"]] = {
            "strain_name": g["strain_name"],
            "parent1": g.get("parent1", ""),
            "parent2": g.get("parent2", ""),
            "dispensary": g.get("dispensary", ""),
            "source": "Menu Description"
        }

print(f"Total unique: {len(all_genetics)} strains")

# Save
output = {
    "consolidated_date": "2026-01-20T04:54:00Z",
    "total": len(all_genetics),
    "genetics": list(all_genetics.values())
}

with open("final_consolidated_genetics.json", "w") as f:
    json.dump(output, f, indent=2)

print("\nSaved to final_consolidated_genetics.json")
