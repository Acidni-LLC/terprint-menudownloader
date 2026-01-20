"""Generate comprehensive genetics report"""
import json
from datetime import datetime
from collections import Counter

# Load genetics data
with open("all_genetics_20260120.json", "r") as f:
    data = json.load(f)

strains = data["strains"]

# Analysis
print("=" * 80)
print("TERPRINT CANNABIS GENETICS REPORT")
print("=" * 80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Extraction Date: {data['extraction_date'][:10]}")
print(f"Total Unique Strains: {data['total_strains']}")
print()

# By Dispensary
print("STRAINS BY DISPENSARY")
print("-" * 80)
for disp, count in sorted(data["by_dispensary"].items()):
    pct = (count / data['total_strains']) * 100
    print(f"  {disp.upper():15} {count:3} strains ({pct:5.1f}%)")
print()

# Most common parents
print("MOST COMMON PARENT STRAINS (Top 15)")
print("-" * 80)
all_parents = []
for strain in strains:
    all_parents.append(strain["parent1"])
    all_parents.append(strain["parent2"])

parent_counts = Counter(all_parents)
for parent, count in parent_counts.most_common(15):
    print(f"  {parent:35} {count:2} crosses")
print()

# Strain type distribution
print("STRAIN TYPE DISTRIBUTION")
print("-" * 80)
type_counts = Counter(s.get("strain_type") for s in strains if s.get("strain_type"))
for stype, count in sorted(type_counts.items()):
    if stype:
        pct = (count / len([s for s in strains if s.get("strain_type")])) * 100
        print(f"  {stype.capitalize():15} {count:3} strains ({pct:5.1f}%)")
print()

# Full strain listing
print("COMPLETE STRAIN LISTING (Alphabetical)")
print("=" * 80)
for s in sorted(strains, key=lambda x: x["strain_name"]):
    parent_str = f"{s['parent1']} x {s['parent2']}"
    disp = f"({s['dispensary']})"
    print(f"{s['strain_name']:35} {parent_str:45} {disp:10}")

# Save report
report_file = f"genetics_report_{datetime.now().strftime('%Y%m%d')}.txt"
print(f"\n{'=' * 80}")
print(f"Report saved to: {report_file}")
