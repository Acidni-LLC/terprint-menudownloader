"""
Genetics Scraper for Terprint Menu Downloader

Extracts strain genetics/lineage from dispensary product data.
Supports multiple dispensaries with format-specific extraction.

Usage:
    from terprint_menu_downloader.genetics import GeneticsScraper
    
    scraper = GeneticsScraper()
    
    # Extract from real-time download
    result = scraper.extract_from_menu(menu_data, dispensary="trulieve")
    
    # Extract from stored blob
    result = await scraper.extract_from_blob("dispensaries/trulieve/2026/01/19/menu.json")
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from .models import StrainGenetics, GeneticsExtractionResult

logger = logging.getLogger(__name__)


class GeneticsScraper:
    """
    Extracts genetics/lineage information from cannabis product data.
    
    Supports Terprint dispensaries:
    - Trulieve: Lineage in strain_description HTML
    - Cookies: Genetics in informations dict or description
    - Curaleaf: Lineage in description field
    - MUV: Genetics/cross in description
    - Flowery: Various description fields
    - Sunburn: Similar to MUV
    """
    
    # Common patterns for extracting lineage from text
    LINEAGE_PATTERNS = [
        # Pattern 1: "Lineage: Parent1 x Parent2" (explicit lineage field - most reliable)
        # Captures the two parents separately, stops at opening paren, period, newline, or end
        r"lineage:\s*([A-Za-z0-9#\s&']+?)\s*[xX×]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n]|$)",
    ]
    
    # Pattern to split parent strains (include × Unicode character)
    CROSS_SPLIT_PATTERN = r"\s*[xX×]\s*"
    
    def __init__(self, enable_logging: bool = True, enable_page_scraping: bool = False):
        self.enable_logging = enable_logging
        self.enable_page_scraping = enable_page_scraping
        self._seen_strains: Dict[str, StrainGenetics] = {}
        
        # Initialize product page scrapers (lazy-loaded)
        self._page_scrapers = None
        if enable_page_scraping:
            try:
                from .scrapers.cookies import CookiesScraper
                from .scrapers.flowery import FloweryScraper
                from .scrapers.curaleaf import CuraleafScraper
                
                self._page_scrapers = {
                    "cookies": CookiesScraper(rate_limit_seconds=2.0),
                    "flowery": FloweryScraper(rate_limit_seconds=2.0),
                    "curaleaf": CuraleafScraper(rate_limit_seconds=2.0)
                }
                logger.info("[SCRAPER] Product page scraping enabled for Cookies, Flowery, Curaleaf")
            except ImportError as e:
                logger.warning(f"[SCRAPER] Could not load product page scrapers: {e}")
    
    def extract_from_menu(
        self,
        menu_data: Dict[str, Any],
        dispensary: str,
        source_file: Optional[str] = None
    ) -> GeneticsExtractionResult:
        """
        Extract genetics from menu data.
        
        Args:
            menu_data: Menu JSON data from downloader
            dispensary: Dispensary name (trulieve, cookies, etc.)
            source_file: Optional source file path for tracking
            
        Returns:
            GeneticsExtractionResult with extracted genetics
        """
        result = GeneticsExtractionResult(
            source_file=source_file,
            dispensary=dispensary,
        )
        
        # Route to dispensary-specific extractor
        disp_lower = dispensary.lower()
        
        try:
            if "trulieve" in disp_lower:
                genetics = self._extract_trulieve(menu_data, source_file)
            elif "cookies" in disp_lower:
                genetics = self._extract_cookies(menu_data, source_file)
            elif "curaleaf" in disp_lower:
                genetics = self._extract_curaleaf(menu_data, source_file)
            elif "muv" in disp_lower or "müv" in disp_lower:
                genetics = self._extract_muv(menu_data, source_file)
            elif "flowery" in disp_lower:
                genetics = self._extract_flowery(menu_data, source_file)
            elif "sunburn" in disp_lower:
                genetics = self._extract_sunburn(menu_data, source_file)
            else:
                genetics = self._extract_generic(menu_data, source_file, dispensary)
            
            # Deduplicate by strain slug
            seen = set()
            unique_genetics = []
            for g in genetics:
                if g.strain_slug not in seen:
                    seen.add(g.strain_slug)
                    g.source_dispensary = dispensary
                    unique_genetics.append(g)
            
            result.genetics_found = unique_genetics
            result.unique_strains = len(unique_genetics)
            result.products_with_genetics = len([g for g in genetics if g.parent_1])
            
        except Exception as e:
            logger.error(f"Error extracting genetics from {dispensary}: {e}")
            result.errors.append(str(e))
        
        return result
    
    def extract_from_product(
        self,
        product: Dict[str, Any],
        dispensary: str,
        source_file: Optional[str] = None
    ) -> Optional[StrainGenetics]:
        """
        Extract genetics from a single product.
        
        Args:
            product: Single product dict
            dispensary: Dispensary name
            source_file: Optional source file
            
        Returns:
            StrainGenetics if genetics found, None otherwise
        """
        # Wrap in menu format and extract
        menu_data = {"products": [product]}
        result = self.extract_from_menu(menu_data, dispensary, source_file)
        
        if result.genetics_found:
            return result.genetics_found[0]
        return None
    
    def _extract_product_url(self, product: Dict[str, Any], dispensary: str) -> Optional[str]:
        """Extract product detail page URL from menu data."""
        disp_lower = dispensary.lower()
        
        if "cookies" in disp_lower:
            return product.get("link") or product.get("url")
        elif "flowery" in disp_lower:
            slug = product.get("slug")
            return f"https://theflowery.co/product/{slug}/" if slug else None
        elif "curaleaf" in disp_lower:
            return product.get("detail_url")
        
        return None
    
    def _scrape_genetics_from_url(
        self,
        url: str,
        product_name: str,
        dispensary: str,
        source_file: Optional[str] = None
    ) -> Optional[StrainGenetics]:
        """Scrape genetics from a product detail page URL."""
        if not self.enable_page_scraping or not self._page_scrapers:
            return None
        
        disp_lower = dispensary.lower()
        scraper_key = None
        
        if "cookies" in disp_lower:
            scraper_key = "cookies"
        elif "flowery" in disp_lower:
            scraper_key = "flowery"
        elif "curaleaf" in disp_lower:
            scraper_key = "curaleaf"
        
        if not scraper_key or scraper_key not in self._page_scrapers:
            return None
        
        try:
            result = self._page_scrapers[scraper_key].scrape_product(url)
            if result and result.get("parent_1"):
                # Convert to StrainGenetics
                return StrainGenetics(
                    strain_name=product_name,
                    parent_1=result["parent_1"],
                    parent_2=result.get("parent_2"),
                    source_url=url,
                    source_dispensary=dispensary,
                    source_file=source_file
                )
        except Exception as e:
            logger.debug(f"[SCRAPER] Page scraping failed for {url}: {e}")
        
        return None
    
    def _parse_lineage(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse parent strains from lineage text.
        
        Args:
            text: Text containing lineage info
            
        Returns:
            Tuple of (parent_1, parent_2) or (None, None)
        """
        if not text:
            return None, None
        
        # Skip proprietary genetics
        if "proprietary" in text.lower():
            return None, None
        
        # Normalize and clean leading labels/punctuation
        cleaned = text.strip()
        cleaned = re.sub(r"^(?:lineage|genetics|cross|parentage|parents?)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^[-\s]+", "", cleaned)

        # Try splitting on cross symbols (x, X)
        parents = re.split(self.CROSS_SPLIT_PATTERN, cleaned)
        
        if len(parents) >= 2:
            parent_1 = parents[0].strip().strip("()")
            parent_2 = parents[1].strip().strip("()")
            
            # Clean up parent names (remove trailing parens content)
            parent_1 = re.sub(r"\s*\([^)]*\)\s*$", "", parent_1).strip()
            parent_2 = re.sub(r"\s*\([^)]*\)\s*$", "", parent_2).strip()
            
            # Validate - parents should be reasonable length
            if parent_1 and parent_2 and len(parent_1) >= 2 and len(parent_2) >= 2:
                return parent_1, parent_2
        
        return None, None
    
    def _extract_lineage_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract lineage from description text using patterns.
        
        Args:
            text: Description or genetics text
            
        Returns:
            Tuple of (parent_1, parent_2) or (None, None)
        """
        if not text:
            return None, None
        
        # Skip complex crosses (3-way, 4-way)
        if "mixed with" in text.lower():
            return None, None
        
        # Try each pattern
        for pattern in self.LINEAGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                groups = match.groups()
                # Pattern captured both parents separately
                if len(groups) >= 2 and groups[0] and groups[1]:
                    p1 = groups[0].strip()
                    p2 = groups[1].strip()
                    if p1 and p2 and len(p1) >= 2 and len(p2) >= 2:
                        return p1, p2
                # Pattern captured full lineage text - need to parse it
                elif len(groups) >= 1 and groups[0]:
                    lineage_text = groups[0].strip()
                    # Remove trailing periods, parenthetical notes
                    lineage_text = re.sub(r"\s*\([^)]*\)\s*$", "", lineage_text)
                    lineage_text = re.sub(r"\s*\.$", "", lineage_text)
                    return self._parse_lineage(lineage_text)
        
        return None, None
    
    # =========================================================================
    # Dispensary-Specific Extractors
    # =========================================================================
    
    def _extract_trulieve(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from Trulieve format.
        
        Trulieve stores lineage in strain_description HTML field:
        <strong>Lineage:</strong> Parent1 x Parent2
        """
        genetics = []
        
        # Navigate to products
        products = data.get("products", [])
        if not products:
            products = data.get("data", {}).get("products", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
                
            attrs = product.get("custom_attributes_product", []) or product.get("attributes", [])
            
            # Extract strain info from attributes
            strain_name = None
            strain_type = None
            description = ""
            
            for attr in attrs:
                code = attr.get("code", "")
                value = attr.get("value", "")
                
                if code == "strain":
                    strain_name = value.strip() if value else None
                elif code == "strain_type":
                    strain_type = value.lower() if value else None
                elif code == "strain_description":
                    description = value or ""
            
            # Get product name
            product_name = product.get("name", "")
            
            if not strain_name:
                strain_name = product_name.split(" - ")[0].strip()
            
            if not strain_name or len(strain_name) < 3:
                continue
            
            # Parse lineage from HTML: <strong>Lineage:</strong> Parent1 x Parent2
            parent_1, parent_2 = None, None
            lineage_match = re.search(
                r"<strong>Lineage:</strong>\s*([^<]+)",
                description,
                re.IGNORECASE
            )
            
            if lineage_match:
                lineage_text = lineage_match.group(1).strip()
                parent_1, parent_2 = self._parse_lineage(lineage_text)
            
            # Also check product name for genetics (e.g., "Lemon Cherry x Cap Junky")
            if not parent_1:
                name_match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+[xX×]\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", product_name)
                if name_match:
                    parent_1 = name_match.group(1).strip()
                    parent_2 = name_match.group(2).strip()
                    # Use the cross name as strain name
                    strain_name = f"{parent_1} x {parent_2}"
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    strain_type=strain_type,
                    description=description[:500] if description else None,
                    source_file=source_file,
                    source_url="trulieve.com",
                ))
        
        return genetics
    
    def _extract_cookies(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from Cookies format.
        
        Cookies may have genetics in:
        - product.informations.genetics
        - product.informations.lineage
        - product.description
        """
        genetics = []
        
        products = data.get("products", {})
        if isinstance(products, dict):
            products = products.get("results", [])
        if not products:
            products = data.get("results", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
                
            strain_name = product.get("name", "").split(" - ")[0].strip()
            if not strain_name or len(strain_name) < 3:
                continue
            
            strain_type = product.get("strain_type", "").lower() or None
            parent_1, parent_2 = None, None
            
            # Check informations dict
            info = product.get("informations", {})
            if isinstance(info, dict):
                # Cookies uses "cross" field for genetics (e.g., "Lemon Cherry Gelato x Pina Acai")
                genetics_text = info.get("cross") or info.get("genetics") or info.get("lineage") or ""
                if genetics_text:
                    parent_1, parent_2 = self._parse_lineage(genetics_text)
            
            # Fallback to description
            if not parent_1:
                desc = product.get("description", "")
                if desc:
                    parent_1, parent_2 = self._extract_lineage_from_text(desc)
            
            # Fallback to product page scraping
            if not parent_1 and self.enable_page_scraping:
                product_url = self._extract_product_url(product, "cookies")
                if product_url:
                    scraped = self._scrape_genetics_from_url(product_url, strain_name, "cookies", source_file)
                    if scraped:
                        genetics.append(scraped)
                        continue
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    strain_type=strain_type,
                    source_file=source_file,
                    source_url="cookiesflorida.co",
                ))
        
        return genetics
    
    def _extract_curaleaf(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from Curaleaf format.
        
        Curaleaf has lineage in product description field.
        """
        genetics = []
        
        products = data.get("products", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
                
            strain_name = product.get("strain") or product.get("name", "").split(" - ")[0].strip()
            if not strain_name or len(strain_name) < 3:
                continue
            
            strain_type = product.get("strain_type", "").lower() or None
            parent_1, parent_2 = None, None
            
            desc = product.get("description", "")
            if desc:
                parent_1, parent_2 = self._extract_lineage_from_text(desc)
            
            # Fallback to product page scraping
            if not parent_1 and self.enable_page_scraping:
                product_url = self._extract_product_url(product, "curaleaf")
                if product_url:
                    scraped = self._scrape_genetics_from_url(product_url, strain_name, "curaleaf", source_file)
                    if scraped:
                        genetics.append(scraped)
                        continue
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    strain_type=strain_type,
                    source_file=source_file,
                    source_url="curaleaf.com",
                ))
        
        return genetics
    
    def _extract_muv(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from MÜV format.
        
        MÜV has nested product structure with genetics in description.
        """
        genetics = []
        
        # MÜV blobs have structure: data.products.list
        menu_data = data.get("data", data)  # Handle both direct and nested formats
        products = menu_data.get("products", {}).get("list", [])
        if not products:
            # Fallback formats
            products = data.get("products", {}).get("list", [])
        if not products:
            products = menu_data.get("products", {}).get("items", [])
        if not products:
            products = data.get("items", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
                
            strain_name = product.get("name", "").split(" - ")[0].strip()
            if not strain_name or len(strain_name) < 3:
                continue
            
            parent_1, parent_2 = None, None
            desc = product.get("description", "")
            
            if desc:
                parent_1, parent_2 = self._extract_lineage_from_text(desc)
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    source_file=source_file,
                    source_url="getmuv.com",
                ))
        
        return genetics
    
    def _extract_flowery(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from Flowery format.
        
        Flowery structure:
        {
          "strain": {
            "id": 3258,
            "name": "Zourz",
            "slug": "zourz",
            "lineage": "hybrid/indica"  # or "Parent1 x Parent2"
          }
        }
        """
        genetics = []
        
        products = data.get("products", [])
        if isinstance(products, dict):
            products = products.get("items", []) or products.get("results", [])
        
        for product in products:
            if not isinstance(product, dict):
                continue
            
            # Flowery has strain as an object
            strain_obj = product.get("strain")
            if isinstance(strain_obj, dict):
                strain_name = strain_obj.get("name")
                lineage = strain_obj.get("lineage", "")
            elif isinstance(strain_obj, str):
                strain_name = strain_obj
                lineage = ""
            else:
                strain_name = product.get("name", "").split(" - ")[0].strip()
                lineage = ""
                
            if not strain_name or len(strain_name) < 3:
                continue
            
            parent_1, parent_2 = None, None
            
            # Extract from lineage field first (e.g., "Parent1 x Parent2")
            if lineage and isinstance(lineage, str):
                # Skip generic lineage types like "hybrid/indica"
                if "/" in lineage and not (" x " in lineage.lower() or " × " in lineage):
                    lineage = ""  # This is just strain type, not lineage
                else:
                    parent_1, parent_2 = self._parse_lineage(lineage)
            
            # Fallback to description fields if no lineage in strain object
            if not parent_1:
                for field in ["description", "strain_description", "genetics"]:
                    desc = product.get(field, "")
                    if desc and isinstance(desc, str):
                        parent_1, parent_2 = self._extract_lineage_from_text(desc)
                        if parent_1:
                            break
            
            # Fallback to product page scraping
            if not parent_1 and self.enable_page_scraping:
                product_url = self._extract_product_url(product, "flowery")
                if product_url:
                    scraped = self._scrape_genetics_from_url(product_url, strain_name, "flowery", source_file)
                    if scraped:
                        genetics.append(scraped)
                        continue
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    source_file=source_file,
                    source_url="flowery.com",
                ))
        
        return genetics
    
    def _extract_sunburn(self, data: Dict, source_file: Optional[str]) -> List[StrainGenetics]:
        """
        Extract genetics from Sunburn format.
        Similar to MÜV.
        """
        return self._extract_muv(data, source_file)
    
    def _extract_generic(
        self,
        data: Dict,
        source_file: Optional[str],
        dispensary: str
    ) -> List[StrainGenetics]:
        """
        Generic genetics extraction for unknown formats.
        
        Tries common product array locations and description fields.
        """
        genetics = []
        
        # Find products array
        products = []
        if isinstance(data.get("products"), list):
            products = data["products"]
        elif isinstance(data.get("products"), dict):
            products = data["products"].get("items", []) or data["products"].get("results", [])
        elif isinstance(data.get("items"), list):
            products = data["items"]
        elif isinstance(data.get("results"), list):
            products = data["results"]
        
        for product in products:
            if not isinstance(product, dict):
                continue
            
            # Find strain name
            strain_name = (
                product.get("strain") or
                product.get("strain_name") or
                product.get("name", "").split(" - ")[0].strip()
            )
            
            if not strain_name or len(strain_name) < 3:
                continue
            
            # Try to find lineage in various text fields
            parent_1, parent_2 = None, None
            
            for key in ["description", "strain_description", "genetics", "lineage", "details"]:
                text = product.get(key, "")
                if text and isinstance(text, str):
                    parent_1, parent_2 = self._extract_lineage_from_text(text)
                    if parent_1:
                        break
            
            if parent_1 and parent_2:
                genetics.append(StrainGenetics(
                    strain_name=strain_name,
                    strain_slug=StrainGenetics.normalize_strain_name(strain_name),
                    parent_1=parent_1,
                    parent_2=parent_2,
                    source_file=source_file,
                    source_url=f"{dispensary}",
                ))
        
        return genetics
