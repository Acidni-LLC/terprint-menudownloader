"""
Main script to extract genetics from ALL dispensary product pages
This will scrape 100s-1000s of strain genetics from live websites
"""
import json
import time
from extract_product_urls import ProductURLExtractor
from genetics_webscraper import GeneticsWebScraper


def main():
    print("\n" + "="*90)
    print(" TERPRINT GENETICS WEB SCRAPING - FULL EXTRACTION")
    print("="*90)
    
    # Configuration
    dispensaries = ['muv', 'cookies', 'curaleaf', 'flowery']  # Skip Trulieve (uses batch data)
    max_files_per_dispensary = 20  # Limit menu files to extract URLs from
    max_products_per_dispensary = 100  # Limit products to scrape
    
    # Step 1: Extract product URLs from menu data
    print("\n STEP 1: Extracting product URLs from menu data...")
    extractor = ProductURLExtractor()
    
    all_products_by_dispensary = {}
    for dispensary in dispensaries:
        print(f"\n--- {dispensary.upper()} ---")
        products = extractor.extract_all_urls(dispensary, max_files=max_files_per_dispensary)
        
        # Limit to avoid overwhelming the scraper
        products = products[:max_products_per_dispensary]
        all_products_by_dispensary[dispensary] = products
        
        print(f" {len(products)} product URLs ready for scraping")
    
    total_products = sum(len(p) for p in all_products_by_dispensary.values())
    print(f"\n Total products to scrape: {total_products}")
    
    if total_products == 0:
        print("\n WARNING: No product URLs found. Check menu data availability.")
        return
    
    # Step 2: Scrape product pages for genetics
    print("\n STEP 2: Scraping product pages for genetics...")
    print("This may take several minutes...")
    
    scraper = GeneticsWebScraper(max_workers=10)
    all_genetics = []
    
    for dispensary, products in all_products_by_dispensary.items():
        if not products:
            continue
            
        print(f"\n--- Scraping {dispensary.upper()} ({len(products)} products) ---")
        
        genetics = scraper.scrape_urls(products, dispensary)
        all_genetics.extend(genetics)
        
        success_rate = (len(genetics)/len(products)*100) if products else 0
        print(f" Extracted genetics from {len(genetics)} products ({success_rate:.1f}% success rate)")
        
        # Rate limiting between dispensaries
        time.sleep(5)
    
    # Step 3: Save results
    print("\n STEP 3: Saving results...")
    
    scraper.results = all_genetics
    output_file = f"web_scraped_genetics_{time.strftime('%Y%m%d_%H%M%S')}.json"
    scraper.save_results(output_file)
    
    # Print summary
    print("\n" + "="*90)
    print(" EXTRACTION COMPLETE")
    print("="*90)
    print(f"\nTotal genetics extracted: {len(all_genetics)}")
    print("\nBreakdown by dispensary:")
    
    by_dispensary = {}
    for g in all_genetics:
        by_dispensary[g.dispensary] = by_dispensary.get(g.dispensary, 0) + 1
    
    for disp, count in sorted(by_dispensary.items()):
        print(f"  {disp}: {count}")
    
    print(f"\n Results saved to: {output_file}")
    print("\nNext steps:")
    print("1. Review the extracted genetics")
    print("2. Import to database using genetics_import.sql")
    print("3. Integrate with AI recommender")
    
    return output_file


if __name__ == "__main__":
    try:
        output_file = main()
        print(f"\n Success! Check {output_file} for results.")
    except Exception as e:
        print(f"\n Error: {e}")
        import traceback
        traceback.print_exc()
