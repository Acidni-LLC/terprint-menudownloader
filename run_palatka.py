"""Download all 3 categories for the Palatka Green Dragon store."""

import json
import os

from terprint_menu_downloader.dispensaries.green_dragon.scraper import GreenDragonStoreScraper
from terprint_menu_downloader.dispensaries.green_dragon.config import get_store_by_slug, FL_CATEGORIES

store = get_store_by_slug("palatka")
scraper = GreenDragonStoreScraper()
result = scraper.scrape_store(store, categories=FL_CATEGORIES, include_coa=False)

products = result.get("products", [])
print(f"\nTotal products: {len(products)}")

# Count by category
cats = {}
for p in products:
    c = p.get("category", "unknown")
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")

# Show first 5 per category
for cat in sorted(cats.keys()):
    print(f"\n--- {cat} ---")
    cat_products = [p for p in products if p.get("category") == cat]
    for p in cat_products[:5]:
        name = p.get("name", "?")
        thc = p.get("thc_percent", "?")
        brand = p.get("brand", "?")
        strain = p.get("strain_type", "?")
        coa = "Y" if p.get("coa_url") else "N"
        price = p.get("price", "?")
        weight = p.get("weight", "?")
        print(f"  {name:40s} THC:{thc:>6}%  {strain:8s}  ${price}  {weight}  Brand:{brand}  COA:{coa}")

# Save full results
os.makedirs("output/palatka", exist_ok=True)
outpath = "output/palatka/palatka_all_categories.json"
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)
print(f"\nSaved to {outpath} ({len(products)} products)")
