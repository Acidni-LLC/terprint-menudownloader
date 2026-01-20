"""
Product page scraping integration for genetics backfill.

This enhances the genetics backfill to:
1. Try extracting genetics from menu API data (Trulieve pattern)
2. Fall back to scraping product detail pages (Cookies, Flowery, Curaleaf)
"""
import sys
sys.path.insert(0, "src")

from terprint_menu_downloader.genetics.scrapers.cookies import CookiesScraper
from terprint_menu_downloader.genetics.scrapers.flowery import FloweryScraper  
from terprint_menu_downloader.genetics.scrapers.curaleaf import CuraleafScraper

# Initialize scrapers
scrapers = {
    "cookies": CookiesScraper(rate_limit_seconds=2.0),
    "flowery": FloweryScraper(rate_limit_seconds=2.0),
    "curaleaf": CuraleafScraper(rate_limit_seconds=2.0)
}

def extract_product_url(product: dict, dispensary: str) -> str:
    """Extract product detail URL from menu data."""
    if dispensary == "cookies":
        return product.get("link") or product.get("url")
    elif dispensary == "flowery":
        slug = product.get("slug")
        return f"https://theflowery.co/product/{slug}/" if slug else None
    elif dispensary == "curaleaf":
        return product.get("detail_url")
    return None

def scrape_genetics_from_url(url: str, dispensary: str) -> dict:
    """Scrape genetics from a product detail page."""
    if not url or dispensary not in scrapers:
        return None
    
    try:
        result = scrapers[dispensary].scrape_product(url)
        return result
    except Exception as e:
        print(f"[ERROR] Scraping failed for {url}: {e}")
        return None

# Test with sample data
print("=== Product Page Scraping Integration Ready ===\n")
print("Scrapers initialized for:")
for dispensary in scrapers.keys():
    print(f"  - {dispensary.title()}")

print("\n Ready to integrate into genetics backfill!")
print("\nUsage in backfill.py:")
print("  1. Extract genetics from API data (existing Trulieve logic)")
print("  2. If no genetics, extract product URL")
print("  3. Scrape product page for genetics")
print("  4. Cache results to avoid re-scraping")
