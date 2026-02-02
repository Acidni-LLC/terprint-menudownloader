"""
Green Dragon Cannabis Company - Web Scraper
Scrapes Squarespace-based menu pages for strain information
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import httpx
from bs4 import BeautifulSoup
import json

from .config import GREEN_DRAGON_CONFIG, StoreConfig


logger = logging.getLogger(__name__)


class GreenDragonScraper:
    """Scrapes Green Dragon Squarespace pages for product menus"""
    
    def __init__(self, config=None):
        self.config = config or GREEN_DRAGON_CONFIG
        self.session: Optional[httpx.AsyncClient] = None
        self.base_url = self.config.base_url
        
    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            headers={
                "User-Agent": self.config.user_agent,
                "Accept-Language": self.config.accept_language,
            },
            timeout=self.config.request_timeout_seconds,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
        return False
    
    async def get_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting"""
        try:
            await asyncio.sleep(self.config.rate_limit_ms / 1000)
            response = await self.session.get(url)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def parse_strain_page(self, html: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single strain/product page
        Extracts: name, type (Indica/Sativa/Hybrid), effects, flavors
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Find strain name
            name_elem = soup.select_one(self.config.strain_name_selector)
            if not name_elem:
                return None
            
            name = name_elem.get_text(strip=True)
            
            # Find strain type (Indica/Sativa/Hybrid)
            type_elem = soup.select_one(self.config.strain_type_selector)
            strain_type = type_elem.get_text(strip=True) if type_elem else None
            
            # Find effects - look for any content after "Effects:" label
            effects = []
            content_elems = soup.select(self.config.effects_selector)
            for i, elem in enumerate(content_elems):
                text = elem.get_text(strip=True)
                # If previous element contains "Effects:", this is effects
                if i > 0:
                    prev_text = content_elems[i-1].get_text(strip=True)
                    if "Effect" in prev_text:
                        # Parse comma-separated effects
                        effects = [e.strip() for e in text.split(",")]
                        break
            
            # Try alternate method - find spans/paragraphs with effect patterns
            if not effects:
                for p in soup.find_all(['p', 'span']):
                    text = p.get_text(strip=True)
                    if any(eff in text for eff in ["Relaxed", "Energetic", "Happy", "Calm", "Uplifted"]):
                        # This paragraph likely contains effects
                        effects = [e.strip() for e in text.split(",")]
                        break
            
            return {
                "name": name,
                "type": strain_type,
                "effects": effects,
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to parse strain page: {e}")
            return None
    
    async def scrape_location(self, store: StoreConfig) -> Dict[str, Any]:
        """
        Scrape a single location's menu
        Returns: { products: [...], store: StoreConfig, scraped_at: ... }
        """
        try:
            url = store.url
            logger.info(f"Scraping {store.name} from {url}")
            
            html = await self.get_page(url)
            if not html:
                logger.warning(f"Failed to fetch page for {store.name}")
                return {
                    "store": store,
                    "products": [],
                    "status": "failed",
                    "error": "Failed to fetch page",
                    "scraped_at": datetime.utcnow().isoformat(),
                }
            
            # Parse the main menu page
            soup = BeautifulSoup(html, "html.parser")
            products = []
            
            # Look for product containers - Squarespace uses various structures
            # Try to find product divs or list items
            product_containers = soup.select("[data-product], .product, [class*='product']")
            
            if not product_containers:
                # Fallback: look for heading + description patterns
                for elem in soup.select("h2, h3, h4"):
                    text = elem.get_text(strip=True)
                    if len(text) > 2 and len(text) < 50:
                        # Might be a product name
                        products.append({
                            "name": text,
                            "category": "flower",
                            "source_url": url,
                            "scraped_at": datetime.utcnow().isoformat(),
                        })
            else:
                # Parse each product container
                for container in product_containers:
                    product_name = container.select_one("h2, h3, .product-name")
                    if product_name:
                        products.append({
                            "name": product_name.get_text(strip=True),
                            "category": "flower",
                            "source_url": url,
                            "scraped_at": datetime.utcnow().isoformat(),
                        })
            
            return {
                "store": store,
                "products": products,
                "status": "success",
                "product_count": len(products),
                "scraped_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error scraping {store.name}: {e}")
            return {
                "store": store,
                "products": [],
                "status": "error",
                "error": str(e),
                "scraped_at": datetime.utcnow().isoformat(),
            }
    
    async def scrape_all_locations(
        self,
        stores: List[StoreConfig],
        concurrent_limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple locations with concurrency control
        """
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def scrape_with_limit(store):
            async with semaphore:
                return await self.scrape_location(store)
        
        tasks = [scrape_with_limit(store) for store in stores]
        results = await asyncio.gather(*tasks)
        return results


# Standalone functions for backward compatibility
async def scrape_green_dragon_location(store: StoreConfig) -> Dict[str, Any]:
    """Scrape a single Green Dragon location"""
    async with GreenDragonScraper() as scraper:
        return await scraper.scrape_location(store)


async def scrape_green_dragon_all(stores: List[StoreConfig]) -> List[Dict[str, Any]]:
    """Scrape all Green Dragon locations"""
    async with GreenDragonScraper() as scraper:
        return await scraper.scrape_all_locations(stores)
