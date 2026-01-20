import sys
sys.path.insert(0, "src")
from terprint_menu_downloader.genetics.scraper import GeneticsScraper

scraper = GeneticsScraper(enable_page_scraping=True)
print(" GeneticsScraper with product page scraping initialized successfully")
print(f"   Page scrapers enabled: {scraper._page_scrapers is not None}")
if scraper._page_scrapers:
    print(f"   Scrapers loaded: {list(scraper._page_scrapers.keys())}")
