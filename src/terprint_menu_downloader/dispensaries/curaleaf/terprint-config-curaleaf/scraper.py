"""
Curaleaf Menu Scraper Module

This module provides the scraping logic for Curaleaf dispensary menus.
Designed for integration with the Menu Downloader pipeline.

Usage:
    from terprint_config.dispensaries.curaleaf import CuraleafScraper
    
    scraper = CuraleafScraper()
    products = scraper.scrape_store_menu("curaleaf-dispensary-tampa")
"""

import httpx
from bs4 import BeautifulSoup
import re
import time
from typing import Optional
from datetime import datetime, timezone

# Import config - handle both package and standalone usage
try:
    from .config import CURALEAF_CONFIG, ProductData, TerpeneData
except ImportError:
    from config import CURALEAF_CONFIG, ProductData, TerpeneData


class CuraleafScraper:
    """Scraper for Curaleaf dispensary menus."""
    
    def __init__(self, config=None):
        self.config = config or CURALEAF_CONFIG
        self.client = None
        self._default_headers = {
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
    
    def __enter__(self):
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()
    
    def _parse_aria_label(self, aria: str) -> Optional[dict]:
        """Parse product info from aria-label attribute."""
        try:
            # Pattern: "Product Name, Category. Size - $Price"
            if ',' not in aria or '$' not in aria:
                return None
            
            parts = aria.split(',', 1)
            if len(parts) < 2:
                return None
            
            name = parts[0].strip()
            rest = parts[1].strip()
            
            # Extract category (before the period)
            cat_match = re.match(r'([^.]+)\.', rest)
            category = cat_match.group(1).strip() if cat_match else None
            
            # Extract size and price
            size_price_match = re.search(
                r'(\d+\.?\d*\s*(?:g|mg|ml|oz|ct|pk|pack)?)\s*(?:/\s*\d+\.?\d*\s*(?:g|mg|ml|oz|ct|pk|pack)?)?\s*-\s*\$(\d+\.?\d*)', 
                rest, 
                re.IGNORECASE
            )
            
            size = size_price_match.group(1).strip() if size_price_match else None
            price = float(size_price_match.group(2)) if size_price_match else None
            
            return {
                'name': name,
                'category': category,
                'weight': size,
                'price': price,
            }
        except Exception:
            return None
    
    def scrape_menu_page(self, store_slug: str) -> list[ProductData]:
        """
        Scrape the menu page for a store.
        Returns basic product info (no terpenes - those require detail page).
        
        Uses aria-label parsing which is proven to work with Curaleaf's HTML.
        """
        if not self.client:
            raise RuntimeError("Scraper must be used as context manager")
        
        url = self.config.get_menu_url(store_slug)
        response = self.client.get(url, headers=self._default_headers)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch menu: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        products = []
        
        # Find all product links with aria-label (proven parsing method)
        product_links = soup.find_all('a', {'aria-label': True})
        
        for link in product_links:
            aria = link.get('aria-label', '')
            
            if not aria or '$' not in aria:
                continue
            
            product_data = self._parse_aria_label(aria)
            if not product_data:
                continue
            
            # Get product ID and URL
            product_id = link.get('id', '').replace('product-', '')
            href = link.get('href', '')
            
            if not href or not product_id:
                continue
            
            product_data['product_id'] = product_id
            product_data['product_slug'] = href.split('/')[-1] if '/' in href else href
            product_data['detail_url'] = f"{self.config.base_url}{href}"
            
            # Extract THC/CBD from card HTML via regex
            card_html = str(link)
            
            thc_match = re.search(r'>THC:\s*([\d.]+)%<', card_html)
            cbd_match = re.search(r'>CBD:\s*([\d.]+)%<', card_html)
            strain_match = re.search(r'>(Indica|Sativa|Hybrid)<', card_html)
            
            product_data['thc_percent'] = float(thc_match.group(1)) if thc_match else None
            product_data['cbd_percent'] = float(cbd_match.group(1)) if cbd_match else None
            product_data['strain_type'] = strain_match.group(1) if strain_match else None
            
            # Extract brand
            brand_match = re.search(r'by<!-- --> <!-- -->([^<]+)<', card_html)
            if brand_match:
                product_data['brand'] = brand_match.group(1).strip()
            
            products.append(product_data)
        
        # Deduplicate by product_id
        seen_ids = set()
        unique_products = []
        for p in products:
            pid = p.get('product_id')
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                unique_products.append(p)
        
        return unique_products
    
    def scrape_product_terpenes(self, detail_url: str) -> dict:
        """
        Scrape terpene data from a product detail page.
        
        Uses regex parsing of embedded JSON which is more reliable than DOM selectors.
        
        Returns dict with:
            - total_terpenes_percent: float or None
            - top_terpenes: str (comma-separated names) or None
            - lab_test_url: str or None
        """
        if not self.client:
            raise RuntimeError("Scraper must be used as context manager")
        
        terpene_data = {
            'total_terpenes_percent': None,
            'top_terpenes': None,
            'terpene_list': [],
            'lab_test_url': None,
        }
        
        try:
            response = self.client.get(detail_url, headers=self._default_headers)
            if response.status_code != 200:
                return terpene_data
            
            text = response.text
            
            # Extract total terpenes from JSON structure
            total_terp_match = re.search(r'"terpenes":\{"value":\[(\d+\.?\d*)\],"unitAbbr":"%"', text)
            if total_terp_match:
                terpene_data['total_terpenes_percent'] = float(total_terp_match.group(1))
            
            # Fallback: HTML display version
            if not terpene_data['total_terpenes_percent']:
                html_terp_match = re.search(r'>Total Terpenes</div><div[^>]*>(\d+\.?\d*)%</div>', text)
                if html_terp_match:
                    terpene_data['total_terpenes_percent'] = float(html_terp_match.group(1))
            
            # Extract top terpenes from description
            top_terp_match = re.search(r'Top Terpenes:\s*([A-Za-z, ]+)', text)
            if top_terp_match:
                top_terps = top_terp_match.group(1).strip()
                if '\\n' in top_terps:
                    top_terps = top_terps.split('\\n')[0].strip()
                terpene_data['top_terpenes'] = top_terps
            
            # Extract individual terpene names from JSON structure
            terp_names = re.findall(r'"terpenes":\[\{[^]]*"name":"([A-Za-z ]+)"', text)
            if terp_names:
                terpene_data['terpene_list'] = list(set(terp_names))
            
            # Extract lab test URL
            lab_match = re.search(r'href="(https://yourcoa\.com/[^"]+)"', text)
            if lab_match:
                terpene_data['lab_test_url'] = lab_match.group(1)
            
        except Exception:
            pass
        
        return terpene_data
    
    def scrape_store_menu_with_terpenes(
        self, 
        store_slug: str, 
        max_products: int = None,
        sample_terpenes: int = None
    ) -> list[ProductData]:
        """
        Scrape a store's full menu with terpene data.
        
        Args:
            store_slug: Store slug (e.g., "curaleaf-dispensary-tampa")
            max_products: Maximum products to return (None = all)
            sample_terpenes: Only fetch terpenes for N products (None = all)
        
        Returns:
            List of products with terpene data populated
        """
        # First get all products from menu page
        products = self.scrape_menu_page(store_slug)
        
        if max_products:
            products = products[:max_products]
        
        # Determine which products to fetch terpenes for
        terpene_count = sample_terpenes if sample_terpenes else len(products)
        
        # Fetch terpene data for products
        for i, product in enumerate(products[:terpene_count]):
            if 'detail_url' in product:
                terpenes = self.scrape_product_terpenes(product['detail_url'])
                product.update(terpenes)
                
                # Rate limiting
                if i < terpene_count - 1:
                    time.sleep(self.config.rate_limit_ms / 1000.0)
        
        return products
    
    def scrape_store_to_terprint_format(
        self,
        store_slug: str,
        store_name: str,
        max_products: int = None,
    ) -> dict:
        """
        Scrape a store and format output for Menu Downloader pipeline.
        
        Returns dict compatible with terprint blob storage format.
        """
        products = self.scrape_store_menu_with_terpenes(store_slug, max_products)
        
        return {
            "dispensary": "curaleaf",
            "store_slug": store_slug,
            "store_name": store_name,
            "state": "FL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "product_count": len(products),
            "products": products,
            "metadata": {
                "platform": self.config.platform,
                "scrape_type": "html",
                "terpene_source": self.config.terpene_source,
            }
        }
