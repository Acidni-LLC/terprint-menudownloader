"""Curaleaf product page scraper."""
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from .base import ProductPageScraper


class CuraleafScraper(ProductPageScraper):
    """Scrape genetics from Curaleaf product pages."""
    
    def extract_genetics(self, soup: BeautifulSoup, product_url: str) -> Optional[Dict[str, Any]]:
        """Extract genetics from Curaleaf product page HTML."""
        genetics = {"url": product_url, "parent_1": None, "parent_2": None}
        
        # Curaleaf structure - check product details sections
        selectors = [
            ".product-info",
            ".product-details",
            "[class*='description']",
            "[class*='lineage']",
            "p", "div"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                
                # Look for genetics keywords
                if re.search(r"lineage|genetics|parent|bred|cross", text, re.IGNORECASE):
                    lineage = self.parse_lineage_pattern(text)
                    if lineage:
                        genetics["parent_1"], genetics["parent_2"] = lineage
                        return genetics
        
        return None
