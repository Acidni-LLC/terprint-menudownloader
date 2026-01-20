"""
Comprehensive Web Scraper for Cannabis Strain Genetics
Extracts parent lineage from dispensary product detail pages
"""
import requests
from bs4 import BeautifulSoup
import time
import re
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class StrainGenetics:
    strain_name: str
    parent1: str
    parent2: str
    dispensary: str
    source_url: str
    strain_type: Optional[str] = None
    extraction_confidence: float = 1.0  # 0.0 to 1.0


class ProductPageScraper:
    """Base scraper for extracting genetics from product pages."""
    
    LINEAGE_PATTERNS = [
        r"lineage[:\s]+([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n<]|$)",
        r"genetics[:\s]+([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n<]|$)",
        r"cross[:\s]+([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n<]|$)",
        r"parent[s]?[:\s]+([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n<]|$)",
        r"([A-Za-z0-9#\s&']{3,30})\s*[xX]\s*([A-Za-z0-9#\s&']{3,30})",
    ]
    
    def __init__(self, rate_limit: float = 2.0, timeout: int = 30):
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL with rate limiting."""
        try:
            time.sleep(self.rate_limit)
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def parse_lineage(self, text: str) -> Optional[Tuple[str, str]]:
        """Extract parent strains from text using regex patterns."""
        for pattern in self.LINEAGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and len(match.groups()) >= 2:
                parent1 = match.group(1).strip()
                parent2 = match.group(2).strip()
                
                # Validate parents (not too short, not numbers only)
                if (len(parent1) >= 2 and len(parent2) >= 2 and
                    not parent1.isdigit() and not parent2.isdigit()):
                    return (parent1, parent2)
        return None
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        """Override in subclass for dispensary-specific extraction."""
        raise NotImplementedError


class TrulieveScraper(ProductPageScraper):
    """Scrape genetics from Trulieve product pages."""
    
    BASE_URL = "https://www.trulieve.com"
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check description and specifications
        for selector in ['.product-description', '.product-info', '[class*="description"]', 'p']:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage(text)
                if lineage:
                    return StrainGenetics(
                        strain_name=strain_name,
                        parent1=lineage[0],
                        parent2=lineage[1],
                        dispensary="trulieve",
                        source_url=url
                    )
        return None


class MuvScraper(ProductPageScraper):
    """Scrape genetics from MÜV product pages."""
    
    BASE_URL = "https://muvfl.com"
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # MÜV has genetics in product description
        for selector in ['.product-details', '.description', '[class*="genetics"]']:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage(text)
                if lineage:
                    return StrainGenetics(
                        strain_name=strain_name,
                        parent1=lineage[0],
                        parent2=lineage[1],
                        dispensary="muv",
                        source_url=url
                    )
        return None


class CookiesScraper(ProductPageScraper):
    """Scrape genetics from Cookies product pages."""
    
    BASE_URL = "https://cookies.co"
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Cookies has genetics in informations or description
        for selector in ['.informations', '.product-description', '[data-genetics]']:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage(text)
                if lineage:
                    # Try to extract strain type
                    strain_type = None
                    type_match = re.search(r'\b(indica|sativa|hybrid|indica hybrid|sativa hybrid)\b', text, re.IGNORECASE)
                    if type_match:
                        strain_type = type_match.group(1).lower()
                    
                    return StrainGenetics(
                        strain_name=strain_name,
                        parent1=lineage[0],
                        parent2=lineage[1],
                        dispensary="cookies",
                        source_url=url,
                        strain_type=strain_type
                    )
        return None


class CuraleafScraper(ProductPageScraper):
    """Scrape genetics from Curaleaf product pages."""
    
    BASE_URL = "https://www.curaleaf.com"
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        soup = BeautifulSoup(html, 'html.parser')
        
        for selector in ['.product-description', '.strain-info', 'article']:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage(text)
                if lineage:
                    return StrainGenetics(
                        strain_name=strain_name,
                        parent1=lineage[0],
                        parent2=lineage[1],
                        dispensary="curaleaf",
                        source_url=url
                    )
        return None


class FloweryScraper(ProductPageScraper):
    """Scrape genetics from The Flowery product pages."""
    
    BASE_URL = "https://theflowery.co"
    
    def extract_genetics(self, html: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        soup = BeautifulSoup(html, 'html.parser')
        
        for selector in ['.product-info', '.description', '[class*="detail"]']:
            elements = soup.select(selector)
            for el in elements:
                text = el.get_text()
                lineage = self.parse_lineage(text)
                if lineage:
                    return StrainGenetics(
                        strain_name=strain_name,
                        parent1=lineage[0],
                        parent2=lineage[1],
                        dispensary="flowery",
                        source_url=url
                    )
        return None


class GeneticsWebScraper:
    """Main scraper orchestrator for all dispensaries."""
    
    def __init__(self, max_workers: int = 5):
        self.scrapers = {
            'trulieve': TrulieveScraper(rate_limit=2.0),
            'muv': MuvScraper(rate_limit=2.0),
            'cookies': CookiesScraper(rate_limit=2.0),
            'curaleaf': CuraleafScraper(rate_limit=2.0),
            'flowery': FloweryScraper(rate_limit=2.0),
        }
        self.max_workers = max_workers
        self.results: List[StrainGenetics] = []
    
    def scrape_product(self, dispensary: str, url: str, strain_name: str) -> Optional[StrainGenetics]:
        """Scrape a single product page."""
        scraper = self.scrapers.get(dispensary)
        if not scraper:
            logger.warning(f"No scraper for dispensary: {dispensary}")
            return None
        
        html = scraper.fetch_page(url)
        if not html:
            return None
        
        return scraper.extract_genetics(html, url, strain_name)
    
    def scrape_urls(self, products: List[Dict[str, str]], dispensary: str) -> List[StrainGenetics]:
        """
        Scrape multiple product pages in parallel.
        
        Args:
            products: List of dicts with 'url' and 'strain_name' keys
            dispensary: Dispensary name
        
        Returns:
            List of successfully extracted genetics
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.scrape_product, dispensary, p['url'], p['strain_name']): p
                for p in products
            }
            
            for future in as_completed(futures):
                product = futures[future]
                try:
                    genetics = future.result()
                    if genetics:
                        results.append(genetics)
                        logger.info(f" Extracted: {genetics.strain_name} = {genetics.parent1}  {genetics.parent2}")
                    else:
                        logger.debug(f" No genetics found for {product['strain_name']}")
                except Exception as e:
                    logger.error(f"Error scraping {product['strain_name']}: {e}")
        
        return results
    
    def save_results(self, filename: str = "web_scraped_genetics.json"):
        """Save results to JSON file."""
        data = {
            "extraction_date": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total_strains": len(self.results),
            "by_dispensary": {},
            "strains": []
        }
        
        # Count by dispensary
        for genetics in self.results:
            disp = genetics.dispensary
            data["by_dispensary"][disp] = data["by_dispensary"].get(disp, 0) + 1
            
            data["strains"].append({
                "strain_name": genetics.strain_name,
                "parent1": genetics.parent1,
                "parent2": genetics.parent2,
                "dispensary": genetics.dispensary,
                "strain_type": genetics.strain_type,
                "source_url": genetics.source_url,
                "confidence": genetics.extraction_confidence
            })
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f" Saved {len(self.results)} genetics to {filename}")
        return filename


if __name__ == "__main__":
    # Example usage
    scraper = GeneticsWebScraper(max_workers=10)
    
    # Example: Scrape some Trulieve products
    trulieve_products = [
        {"url": "https://www.trulieve.com/shop/product-name", "strain_name": "Example Strain"}
    ]
    
    results = scraper.scrape_urls(trulieve_products, "trulieve")
    scraper.results = results
    scraper.save_results("genetics_web_scraped.json")
    
    print(f"\n Extraction complete: {len(results)} strains")
