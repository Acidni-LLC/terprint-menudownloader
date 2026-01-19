"""
Genetics Scraper Module for Terprint Menu Downloader

Extracts strain genetics/lineage information from menu product data
and stores it in CDES-compatible format.

Usage:
    from terprint_menu_downloader.genetics import GeneticsScraper, StrainGenetics
    
    # Extract from a single product
    scraper = GeneticsScraper()
    genetics = scraper.extract_from_product(product_data, dispensary="trulieve")
    
    # Batch process menu data
    all_genetics = scraper.extract_from_menu(menu_data, dispensary="cookies")
    
    # Save to storage
    from terprint_menu_downloader.genetics import GeneticsStorage
    storage = GeneticsStorage()
    await storage.save_genetics(all_genetics)
"""

from .models import StrainGenetics, CDESGenetics, GeneticsExtractionResult
from .scraper import GeneticsScraper
from .storage import GeneticsStorage

__all__ = [
    "StrainGenetics",
    "CDESGenetics",
    "GeneticsExtractionResult",
    "GeneticsScraper",
    "GeneticsStorage",
]
