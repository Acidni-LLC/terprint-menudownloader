"""
Curaleaf Florida Dispensary Configuration

Platform: SweedPOS (HTML Scraping)
Coverage: 65 FL dispensary stores
Terpene Data: ~85% of products have terpene profiles
Discovery Date: December 2025
"""

from typing import TypedDict, Optional
from dataclasses import dataclass


# Type definitions for Menu Downloader compatibility
class TerpeneData(TypedDict, total=False):
    name: str
    percent: float


class ProductData(TypedDict, total=False):
    name: str
    category: str
    brand: str
    strain_type: str
    thc_percent: Optional[float]
    cbd_percent: Optional[float]
    weight: str
    price: str
    total_terpenes_percent: Optional[float]
    top_terpenes: list[TerpeneData]
    lab_test_url: Optional[str]
    detail_url: str
    product_slug: str


class StoreConfig(TypedDict):
    slug: str
    name: str
    internal_name: str
    unique_id: str
    state: str


@dataclass
class CuraleafConfig:
    """Configuration for Curaleaf dispensary scraping."""
    
    # Platform identification
    dispensary_name: str = "Curaleaf"
    platform: str = "SweedPOS"
    platform_type: str = "html_scraping"
    state: str = "FL"
    
    # Base URLs
    base_url: str = "https://curaleaf.com"
    stores_api: str = "/api/dispensaries"
    
    # URL patterns (use .format() with store_slug, product_slug)
    # NOTE: Florida stores use /shop/florida/{slug} pattern
    menu_url_pattern: str = "/shop/florida/{store_slug}"
    product_url_pattern: str = "/shop/florida/{store_slug}/products/{product_slug}"
    
    # Scraping configuration
    requires_detail_scraping: bool = True
    terpene_source: str = "product_detail_page"
    rate_limit_ms: int = 500
    max_products_per_store: int = 500
    
    # Data selectors (CSS/data-testid)
    selectors: dict = None
    
    # Field mappings for terprint schema
    field_mappings: dict = None
    
    def __post_init__(self):
        if self.selectors is None:
            self.selectors = {
                # Menu page selectors - uses aria-label parsing
                "product_link": "a[aria-label]",
                "product_card": "a[data-testid='product-card']",
                "product_name": "[data-testid='product-name']",
                "product_category": "[data-testid='product-category']",
                "product_brand": "[data-testid='product-brand']",
                "product_price": "[data-testid='product-price']",
                "product_thc": "[data-testid='product-thc']",
                "product_weight": "[data-testid='product-weight']",
                
                # Product detail page selectors
                "terpene_section": "[data-testid='terps-section']",
                "total_terpenes": "[data-testid='total-terps']",
                "terpene_row": "[data-testid='terpene-row']",
                "terpene_name": ".terpene-name",
                "terpene_value": ".terpene-value",
                "lab_test_link": "a[href*='yourcoa.com']",
            }
        
        if self.field_mappings is None:
            self.field_mappings = {
                # Source field -> terprint schema field
                "name": "product_name",
                "category": "product_category",
                "brand": "product_brand",
                "strain_type": "strain_type",
                "thc_percent": "thc_percent",
                "cbd_percent": "cbd_percent",
                "weight": "weight",
                "price": "price",
                "total_terpenes_percent": "total_terpenes",
                "top_terpenes": "terpene_profile",
                "lab_test_url": "coa_url",
                "detail_url": "source_url",
            }
    
    def get_menu_url(self, store_slug: str) -> str:
        """Get the full menu URL for a store."""
        return f"{self.base_url}{self.menu_url_pattern.format(store_slug=store_slug)}"
    
    def get_product_url(self, store_slug: str, product_slug: str) -> str:
        """Get the full product detail URL."""
        return f"{self.base_url}{self.product_url_pattern.format(store_slug=store_slug, product_slug=product_slug)}"
    
    def get_stores_url(self, page: int = 1, limit: int = 100) -> str:
        """Get the stores API URL."""
        return f"{self.base_url}{self.stores_api}?page={page}&limit={limit}"
    
    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        return {
            "dispensary_name": self.dispensary_name,
            "platform": self.platform,
            "platform_type": self.platform_type,
            "state": self.state,
            "base_url": self.base_url,
            "stores_api": self.stores_api,
            "menu_url_pattern": self.menu_url_pattern,
            "product_url_pattern": self.product_url_pattern,
            "requires_detail_scraping": self.requires_detail_scraping,
            "terpene_source": self.terpene_source,
            "rate_limit_ms": self.rate_limit_ms,
            "max_products_per_store": self.max_products_per_store,
            "selectors": self.selectors,
            "field_mappings": self.field_mappings,
        }


# Singleton configuration instance
CURALEAF_CONFIG = CuraleafConfig()


# All Florida stores (65 dispensary locations)
FL_STORES: list[StoreConfig] = [
    {"slug": "curaleaf-dispensary-cape-canaveral", "name": "Cape Canaveral", "internal_name": "Cape Canaveral, FL-LMR169", "unique_id": "LMR169", "state": "FL"},
    {"slug": "curaleaf-dispensary-south-miami-dade", "name": "South Miami Dade", "internal_name": "South Miami Dade, FL-LMR001", "unique_id": "LMR001", "state": "FL"},
    {"slug": "curaleaf-tampa-dale-mabry-midtown", "name": "Tampa Dale Mabry Midtown", "internal_name": "Tampa Dale Mabry Midtown, FL-LMR137", "unique_id": "LMR137", "state": "FL"},
    {"slug": "curaleaf-dispensary-ocala", "name": "Ocala", "internal_name": "Curaleaf Ocala (OCA), FL-LMR039", "unique_id": "LMR039", "state": "FL"},
    {"slug": "curaleaf-dispensary-winter-park", "name": "Winter Park", "internal_name": "Winter Park, FL - LMR163", "unique_id": "LMR163", "state": "FL"},
    {"slug": "curaleaf-dispensary-st-augustine", "name": "St. Augustine", "internal_name": "St. Augustine, FL-LMR166", "unique_id": "LMR166", "state": "FL"},
    {"slug": "curaleaf-boca-raton-glades", "name": "Boca Raton Glades", "internal_name": "Curaleaf Boca Glades (BOG), FL-LMR146", "unique_id": "LMR146", "state": "FL"},
    {"slug": "curaleaf-boca-raton-west", "name": "Boca Raton West", "internal_name": "Curaleaf Boca State (BOS) Ration SR 7, FL-LMR150", "unique_id": "LMR150", "state": "FL"},
    {"slug": "curaleaf-dispensary-bonita-springs", "name": "Bonita Springs", "internal_name": "Curaleaf Bonita Springs (BON), FL-LMR037", "unique_id": "LMR037", "state": "FL"},
    {"slug": "curaleaf-dispensary-boynton-beach", "name": "Boynton Beach", "internal_name": "Curaleaf Boynton Beach (BOY), FL-LMR036", "unique_id": "LMR036", "state": "FL"},
    {"slug": "curaleaf-dispensary-bradenton", "name": "Bradenton", "internal_name": "Curaleaf Bradenton (BRA), FL-LMR041", "unique_id": "LMR041", "state": "FL"},
    {"slug": "curaleaf-dispensary-brandon", "name": "Brandon", "internal_name": "Curaleaf Brandon (BRN), FL-LMR042", "unique_id": "LMR042", "state": "FL"},
    {"slug": "curaleaf-dispensary-clearwater", "name": "Clearwater", "internal_name": "Curaleaf Clearwater (CLW), FL-LMR043", "unique_id": "LMR043", "state": "FL"},
    {"slug": "curaleaf-dispensary-daytona-beach", "name": "Daytona Beach", "internal_name": "Curaleaf Daytona Beach (DAY), FL-LMR044", "unique_id": "LMR044", "state": "FL"},
    {"slug": "curaleaf-dispensary-deerfield-beach", "name": "Deerfield Beach", "internal_name": "Curaleaf Deerfield Beach (DEE), FL-LMR045", "unique_id": "LMR045", "state": "FL"},
    {"slug": "curaleaf-dispensary-delray-beach", "name": "Delray Beach", "internal_name": "Curaleaf Delray Beach (DEL), FL-LMR046", "unique_id": "LMR046", "state": "FL"},
    {"slug": "curaleaf-dispensary-fort-lauderdale", "name": "Fort Lauderdale", "internal_name": "Curaleaf Fort Lauderdale (FTL), FL-LMR047", "unique_id": "LMR047", "state": "FL"},
    {"slug": "curaleaf-dispensary-fort-myers", "name": "Fort Myers", "internal_name": "Curaleaf Fort Myers (FTM), FL-LMR048", "unique_id": "LMR048", "state": "FL"},
    {"slug": "curaleaf-dispensary-fort-pierce", "name": "Fort Pierce", "internal_name": "Curaleaf Fort Pierce (FTP), FL-LMR049", "unique_id": "LMR049", "state": "FL"},
    {"slug": "curaleaf-dispensary-gainesville", "name": "Gainesville", "internal_name": "Curaleaf Gainesville (GAI), FL-LMR050", "unique_id": "LMR050", "state": "FL"},
    {"slug": "curaleaf-dispensary-hialeah", "name": "Hialeah", "internal_name": "Curaleaf Hialeah (HIA), FL-LMR051", "unique_id": "LMR051", "state": "FL"},
    {"slug": "curaleaf-dispensary-hollywood", "name": "Hollywood", "internal_name": "Curaleaf Hollywood (HOL), FL-LMR052", "unique_id": "LMR052", "state": "FL"},
    {"slug": "curaleaf-dispensary-jacksonville", "name": "Jacksonville", "internal_name": "Curaleaf Jacksonville (JAX), FL-LMR053", "unique_id": "LMR053", "state": "FL"},
    {"slug": "curaleaf-dispensary-jacksonville-beach", "name": "Jacksonville Beach", "internal_name": "Curaleaf Jacksonville Beach (JXB), FL-LMR054", "unique_id": "LMR054", "state": "FL"},
    {"slug": "curaleaf-dispensary-key-west", "name": "Key West", "internal_name": "Curaleaf Key West (KEY), FL-LMR055", "unique_id": "LMR055", "state": "FL"},
    {"slug": "curaleaf-dispensary-kissimmee", "name": "Kissimmee", "internal_name": "Curaleaf Kissimmee (KIS), FL-LMR056", "unique_id": "LMR056", "state": "FL"},
    {"slug": "curaleaf-dispensary-lake-worth", "name": "Lake Worth", "internal_name": "Curaleaf Lake Worth (LKW), FL-LMR057", "unique_id": "LMR057", "state": "FL"},
    {"slug": "curaleaf-dispensary-lakeland", "name": "Lakeland", "internal_name": "Curaleaf Lakeland (LAK), FL-LMR058", "unique_id": "LMR058", "state": "FL"},
    {"slug": "curaleaf-dispensary-largo", "name": "Largo", "internal_name": "Curaleaf Largo (LAR), FL-LMR059", "unique_id": "LMR059", "state": "FL"},
    {"slug": "curaleaf-dispensary-melbourne", "name": "Melbourne", "internal_name": "Curaleaf Melbourne (MEL), FL-LMR060", "unique_id": "LMR060", "state": "FL"},
    {"slug": "curaleaf-dispensary-miami", "name": "Miami", "internal_name": "Curaleaf Miami (MIA), FL-LMR061", "unique_id": "LMR061", "state": "FL"},
    {"slug": "curaleaf-dispensary-miami-beach", "name": "Miami Beach", "internal_name": "Curaleaf Miami Beach (MIB), FL-LMR062", "unique_id": "LMR062", "state": "FL"},
    {"slug": "curaleaf-dispensary-naples", "name": "Naples", "internal_name": "Curaleaf Naples (NAP), FL-LMR063", "unique_id": "LMR063", "state": "FL"},
    {"slug": "curaleaf-dispensary-north-miami", "name": "North Miami", "internal_name": "Curaleaf North Miami (NMI), FL-LMR064", "unique_id": "LMR064", "state": "FL"},
    {"slug": "curaleaf-dispensary-orlando", "name": "Orlando", "internal_name": "Curaleaf Orlando (ORL), FL-LMR065", "unique_id": "LMR065", "state": "FL"},
    {"slug": "curaleaf-dispensary-orlando-east", "name": "Orlando East", "internal_name": "Curaleaf Orlando East (ORE), FL-LMR066", "unique_id": "LMR066", "state": "FL"},
    {"slug": "curaleaf-dispensary-palm-bay", "name": "Palm Bay", "internal_name": "Curaleaf Palm Bay (PAB), FL-LMR067", "unique_id": "LMR067", "state": "FL"},
    {"slug": "curaleaf-dispensary-palm-harbor", "name": "Palm Harbor", "internal_name": "Curaleaf Palm Harbor (PAH), FL-LMR068", "unique_id": "LMR068", "state": "FL"},
    {"slug": "curaleaf-dispensary-panama-city", "name": "Panama City", "internal_name": "Curaleaf Panama City (PAN), FL-LMR069", "unique_id": "LMR069", "state": "FL"},
    {"slug": "curaleaf-dispensary-pensacola", "name": "Pensacola", "internal_name": "Curaleaf Pensacola (PEN), FL-LMR070", "unique_id": "LMR070", "state": "FL"},
    {"slug": "curaleaf-dispensary-plantation", "name": "Plantation", "internal_name": "Curaleaf Plantation (PLA), FL-LMR071", "unique_id": "LMR071", "state": "FL"},
    {"slug": "curaleaf-dispensary-pompano-beach", "name": "Pompano Beach", "internal_name": "Curaleaf Pompano Beach (POM), FL-LMR072", "unique_id": "LMR072", "state": "FL"},
    {"slug": "curaleaf-dispensary-port-charlotte", "name": "Port Charlotte", "internal_name": "Curaleaf Port Charlotte (PCH), FL-LMR073", "unique_id": "LMR073", "state": "FL"},
    {"slug": "curaleaf-dispensary-port-orange", "name": "Port Orange", "internal_name": "Curaleaf Port Orange (POR), FL-LMR074", "unique_id": "LMR074", "state": "FL"},
    {"slug": "curaleaf-dispensary-port-st-lucie", "name": "Port St. Lucie", "internal_name": "Curaleaf Port St. Lucie (PSL), FL-LMR075", "unique_id": "LMR075", "state": "FL"},
    {"slug": "curaleaf-dispensary-sarasota", "name": "Sarasota", "internal_name": "Curaleaf Sarasota (SAR), FL-LMR076", "unique_id": "LMR076", "state": "FL"},
    {"slug": "curaleaf-dispensary-st-petersburg", "name": "St. Petersburg", "internal_name": "Curaleaf St. Petersburg (STP), FL-LMR077", "unique_id": "LMR077", "state": "FL"},
    {"slug": "curaleaf-dispensary-stuart", "name": "Stuart", "internal_name": "Curaleaf Stuart (STU), FL-LMR078", "unique_id": "LMR078", "state": "FL"},
    {"slug": "curaleaf-dispensary-tallahassee", "name": "Tallahassee", "internal_name": "Curaleaf Tallahassee (TAL), FL-LMR079", "unique_id": "LMR079", "state": "FL"},
    {"slug": "curaleaf-dispensary-tampa", "name": "Tampa", "internal_name": "Curaleaf Tampa (TAM), FL-LMR080", "unique_id": "LMR080", "state": "FL"},
    {"slug": "curaleaf-dispensary-the-villages", "name": "The Villages", "internal_name": "Curaleaf The Villages (VIL), FL-LMR081", "unique_id": "LMR081", "state": "FL"},
    {"slug": "curaleaf-dispensary-vero-beach", "name": "Vero Beach", "internal_name": "Curaleaf Vero Beach (VER), FL-LMR082", "unique_id": "LMR082", "state": "FL"},
    {"slug": "curaleaf-dispensary-west-palm-beach", "name": "West Palm Beach", "internal_name": "Curaleaf West Palm Beach (WPB), FL-LMR083", "unique_id": "LMR083", "state": "FL"},
]


def get_fl_stores() -> list[StoreConfig]:
    """Get all Florida Curaleaf store configurations."""
    return FL_STORES.copy()


def get_store_by_slug(slug: str) -> Optional[StoreConfig]:
    """Get a specific store configuration by slug."""
    for store in FL_STORES:
        if store["slug"] == slug:
            return store
    return None


def get_stores_by_city(city: str) -> list[StoreConfig]:
    """Get all stores in a specific city."""
    city_lower = city.lower()
    return [s for s in FL_STORES if city_lower in s["name"].lower()]
