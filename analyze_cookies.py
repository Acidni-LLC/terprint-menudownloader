from bs4 import BeautifulSoup
import re
import json

# Parse Cookies HTML
with open("cookies_sample.html", "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f.read(), "html.parser")

print("=== COOKIES: Searching for genetics/lineage ===")

# Strategy 1: Search all text for keywords
keywords = ["lineage", "genetics", "cross", "bred", "parent", "strain"]
for keyword in keywords:
    elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
    if elements:
        print(f"\nFound '{keyword}':")
        for elem in elements[:3]:
            parent = elem.parent if hasattr(elem, "parent") else None
            if parent:
                print(f"  Tag: <{parent.name}> Class: {parent.get('class')}")
                text = str(elem).strip()[:200]
                print(f"  Text: {text}")

# Strategy 2: Look for product description sections
print("\n=== Product Description Sections ===")
desc_classes = ["product-description", "product-info", "description", "product__description"]
for cls in desc_classes:
    elements = soup.find_all(class_=re.compile(cls, re.I))
    if elements:
        print(f"\nFound class '{cls}': {len(elements)} elements")
        for elem in elements[:1]:
            print(f"  Text: {elem.get_text()[:300]}")
