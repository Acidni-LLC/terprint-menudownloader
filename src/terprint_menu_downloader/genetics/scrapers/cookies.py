"""Cookies product page scraper."""
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from .base import ProductPageScraper


class CookiesScraper(ProductPageScraper):
    """Scrape genetics from Cookies Florida product pages."""
    
    def extract_genetics(self, soup: BeautifulSoup, product_url: str) -> Optional[Dict[str, Any]]:
        """Extract genetics from Cookies product page HTML."""
        genetics = {"url": product_url, "parent_1": None, "parent_2": None}
        
        # Strategy 1: Look for "Lineage:" or "Genetics:" sections
        for keyword in ["lineage", "genetics", "parent", "cross"]:
            elements = soup.find_all(string=re.compile(keyword, re.IGNORECASE))
            for element in elements:
                text = element.get_text() if hasattr(element, "get_text") else str(element)
                
                # Try to parse "Parent1 x Parent2" pattern
                lineage = self.parse_lineage_pattern(text)
                if lineage:
                    genetics["parent_1"], genetics["parent_2"] = lineage
                    return genetics
                
                # Try to parse "Lineage: Parent1 x Parent2" format
                match = re.search(rf"{keyword}[:\s]+(.*?)(?:[.\n<]|$)", text, re.IGNORECASE)
                if match:
                    lineage_text = match.group(1).strip()
                    lineage = self.parse_lineage_pattern(lineage_text)
                    if lineage:
                        genetics["parent_1"], genetics["parent_2"] = lineage
                        return genetics
        
        # Strategy 2: Check product description/informations fields
        desc_selectors = [
            ".product-description",
            ".informations",
            "[class*='description']",
            "p", "div"
        ]
        
        for selector in desc_selectors:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage_pattern(text)
                if lineage:
                    genetics["parent_1"], genetics["parent_2"] = lineage
                    return genetics
        
        return None  # No genetics found
