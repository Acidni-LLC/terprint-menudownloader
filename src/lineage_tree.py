"""Create visual lineage tree for popular parent strains"""
import json
from collections import defaultdict

with open("all_genetics_20260120.json", "r") as f:
    data = json.load(f)

# Build parent -> children mapping
parent_map = defaultdict(list)
for strain in data["strains"]:
    parent_map[strain["parent1"]].append(strain["strain_name"])
    parent_map[strain["parent2"]].append(strain["strain_name"])

# Display top parent lineages
print("\n" + "=" * 80)
print("GENETICS LINEAGE TREES - Top Parent Strains")
print("=" * 80)

# Get top 8 parents by number of crosses
top_parents = sorted(parent_map.items(), key=lambda x: -len(x[1]))[:8]

for parent, children in top_parents:
    print(f"\n{parent} ({len(children)} crosses)")
    print("" + "" * 78)
    for i, child in enumerate(sorted(children)):
        prefix = "" if i == len(children) - 1 else ""
        print(f"{prefix} {child}")

print("\n" + "=" * 80)
print("CROSS-BREEDING NETWORK")
print("=" * 80)
print("\nStrains with shared parents (genetic siblings):\n")

# Find strains with same parents
siblings = defaultdict(list)
for strain in data["strains"]:
    parents_key = tuple(sorted([strain["parent1"], strain["parent2"]]))
    siblings[parents_key].append(strain["strain_name"])

for parents, strains in siblings.items():
    if len(strains) > 1:
        print(f"{parents[0]}  {parents[1]}:")
        for s in strains:
            print(f"   {s}")
        print()
