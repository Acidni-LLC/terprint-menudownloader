"""Flowery product page scraper."""
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from .base import ProductPageScraper


class FloweryScraper(ProductPageScraper):
    """Scrape genetics from Flowery product pages."""
    
    def extract_genetics(self, soup: BeautifulSoup, product_url: str) -> Optional[Dict[str, Any]]:
        """Extract genetics from Flowery product page HTML."""
        genetics = {"url": product_url, "parent_1": None, "parent_2": None}
        
        # Flowery often uses structured product details
        # Look for lineage in description, details, or specifications
        selectors = [
            ".product-details",
            ".product-description",
            "[class*='lineage']",
            "[class*='genetics']",
            "p", "div", "span"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                
                # Check for lineage keywords
                if re.search(r"lineage|genetics|parent|cross", text, re.IGNORECASE):
                    lineage = self.parse_lineage_pattern(text)
                    if lineage:
                        genetics["parent_1"], genetics["parent_2"] = lineage
                        return genetics
        
        return None
