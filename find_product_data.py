from bs4 import BeautifulSoup
import json
import re

with open("cookies_sample.html", "r", encoding="utf-8") as f:
    html = f.read()
    soup = BeautifulSoup(html, "html.parser")

print("=== Looking for structured product data ===\n")

# Check for Shopify product JSON (common in e-commerce sites)
if "product" in html.lower() and "{" in html:
    # Look for product JSON in script tags
    for script in soup.find_all("script"):
        if script.string and "product" in script.string.lower():
            try:
                # Try to extract JSON objects
                text = script.string
                # Find JSON-like structures
                matches = re.findall(r'\{[^{}]*"[^"]*product[^"]*"[^}]*\}', text, re.IGNORECASE)
                if matches:
                    print(f"Found product JSON in script tag:")
                    for m in matches[:2]:
                        print(f"  {m[:200]}...")
            except:
                pass

# Look for meta tags with product info
print("\n=== Product Meta Tags ===")
for meta in soup.find_all("meta"):
    if meta.get("property") or meta.get("name"):
        prop = meta.get("property") or meta.get("name")
        if "product" in prop.lower() or "description" in prop.lower():
            print(f"{prop}: {meta.get('content', '')[:150]}")

# Show the main product title and surrounding HTML
print("\n=== Product Title Area ===")
title_tag = soup.find("h1")
if title_tag:
    print(f"H1: {title_tag.get_text().strip()}")
    # Get siblings
    if title_tag.parent:
        for sibling in list(title_tag.parent.children)[:5]:
            if hasattr(sibling, "get_text"):
                text = sibling.get_text().strip()
                if text and len(text) > 10:
                    print(f"  Sibling <{sibling.name}>: {text[:100]}")
