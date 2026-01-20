"""
DEMO: Prove web scraping works by scraping a few known product pages
"""
from genetics_webscraper import GeneticsWebScraper


def main():
    print("\n" + "="*90)
    print(" GENETICS WEB SCRAPING - PROOF OF CONCEPT DEMO")
    print("="*90)
    print("\nThis will scrape a few known product pages to prove the concept works")
    
    # Known product URLs that should have genetics
    demo_products = {
        'trulieve': [
            {"url": "https://www.trulieve.com/dispensary-near-me/florida/products/blue-dream-flower", "strain_name": "Blue Dream"},
            {"url": "https://www.trulieve.com/dispensary-near-me/florida/products/purple-punch-flower", "strain_name": "Purple Punch"},
        ],
        'muv': [
            {"url": "https://www.muvfl.com/products/cherry-punch", "strain_name": "Cherry Punch"},
            {"url": "https://www.muvfl.com/products/triangle-kush", "strain_name": "Triangle Kush"},
        ],
        'curaleaf': [
            {"url": "https://shop.curaleaf.com/product/layer-cake", "strain_name": "Layer Cake"},
            {"url": "https://shop.curaleaf.com/product/wedding-cake", "strain_name": "Wedding Cake"},
        ]
    }
    
    scraper = GeneticsWebScraper(max_workers=5)
    all_genetics = []
    
    for dispensary, products in demo_products.items():
        print(f"\n--- Testing {dispensary.upper()} ({len(products)} products) ---")
        
        genetics = scraper.scrape_urls(products, dispensary)
        all_genetics.extend(genetics)
        
        if genetics:
            print(f" SUCCESS! Extracted {len(genetics)} genetics")
            for g in genetics:
                print(f"   {g.strain_name}: {g.parent1}  {g.parent2}")
        else:
            print(f"  No genetics found (URLs may be incorrect or site structure changed)")
    
    print("\n" + "="*90)
    print(f"DEMO COMPLETE: {len(all_genetics)} genetics extracted")
    print("="*90)
    
    if len(all_genetics) > 0:
        print("\n WEB SCRAPING WORKS!")
        print(f"   Successfully extracted genetics from {len(all_genetics)} product pages")
        print("\nNext step: Fix URL extraction for all dispensaries")
        print("Then run full extraction to get 100s-1000s of genetics!")
    else:
        print("\n  No genetics extracted in demo")
        print("Product URLs may need updating or scraping logic needs adjustment")
    
    return all_genetics


if __name__ == "__main__":
    try:
        results = main()
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()
