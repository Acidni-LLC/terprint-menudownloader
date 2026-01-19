"""Base class for product page scrapers."""
import re
import time
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup


class ProductPageScraper(ABC):
    """Base class for scraping individual product pages for genetics."""
    
    def __init__(self, rate_limit_seconds: float = 2.0):
        """Initialize scraper with rate limiting."""
        self.rate_limit = rate_limit_seconds
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TerprintBot/1.0 (Cannabis Data Aggregator; +https://terprint.com)"
        })
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse product page HTML."""
        try:
            self._rate_limit()
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            return None
    
    def extract_genetics(self, soup: BeautifulSoup, product_url: str) -> Optional[Dict[str, Any]]:
        """Extract genetics from parsed HTML. Must be implemented by subclass."""
        pass
    
    def scrape_product(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape genetics from a product page URL."""
        soup = self.fetch_page(url)
        if not soup:
            return None
        return self.extract_genetics(soup, url)
    
    @staticmethod
    def parse_lineage_pattern(text: str) -> Optional[tuple]:
        """Parse Parent1 x Parent2 pattern from text."""
        pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[xX]\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        match = re.search(pattern, text)
        if match:
            return (match.group(1).strip(), match.group(2).strip())
        return None
