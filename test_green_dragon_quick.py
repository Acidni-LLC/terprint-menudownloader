#!/usr/bin/env python3
"""Quick test of Green Dragon scraper functionality"""

import asyncio
import logging
from terprint_menu_downloader.dispensaries.green_dragon import FL_STORES
from terprint_menu_downloader.dispensaries.green_dragon.scraper import GreenDragonScraper

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_green_dragon():
    # Test scraping one store (Avon Park - first in list)
    store = FL_STORES[0]  # Avon Park
    logger.info(f"Testing Green Dragon scraper with store: {store.name} ({store.slug})")
    
    try:
        async with GreenDragonScraper() as scraper:
            result = await scraper.scrape_location(store)
            logger.info(f"✅ Scrape successful!")
            logger.info(f"   Store: {result['store'].name}")
            logger.info(f"   Status: {result['status']}")
            logger.info(f"   Products found: {result['product_count']}")
            if result['products']:
                logger.info(f"   Sample product: {result['products'][0].get('name', 'N/A')}")
            return True
    except Exception as e:
        logger.error(f"❌ Scrape failed: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = asyncio.run(test_green_dragon())
    exit(0 if success else 1)
