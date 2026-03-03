"""
Ayr Wellness Florida Dispensary Configuration

Platform: Dutchie (Embedded iFrame)
Coverage: 22 FL dispensary stores
Terpene Data: Available in Lab Results expandable sections
Discovery Date: February 2026
CRITICAL: Dutchie uses Cloudflare protection - may require browser automation
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
    dutchie_slug: str
    city: str
    state: str


@dataclass
class AyrConfig:
    """Configuration for Ayr Wellness dispensary scraping."""

    # Platform identification
    dispensary_name: str = "Ayr Wellness"
    dispensary_code: str = "ayr"
    grower_id: int = 10
    platform: str = "Dutchie"
    platform_type: str = "embedded_iframe"
    state: str = "FL"

    # Base URLs
    base_url: str = "https://dutchie.com"
    corporate_url: str = "https://ayrwellness.com"
    retail_url: str = "https://ayrdispensaries.com"

    # URL patterns (use .format() with location_slug, product_slug)
    menu_url_pattern: str = "/dispensary/ayr-{location_slug}"
    product_url_pattern: str = "/dispensary/ayr-{location_slug}/product/{product_slug}"
    category_url_pattern: str = "/dispensary/ayr-{location_slug}/products/{category}"

    # Scraping configuration
    requires_age_gate: bool = True
    requires_detail_scraping: bool = True
    terpene_source: str = "product_page_expandable"
    rate_limit_ms: int = 2000  # Higher due to Cloudflare protection
    max_products_per_store: int = 500
    wait_strategy: str = "domcontentloaded"  # networkidle times out

    # Age gate selectors
    age_gate_selectors: list = None

    # Data selectors (CSS selectors)
    selectors: dict = None

    # Field mappings for terprint schema
    field_mappings: dict = None

    def __post_init__(self):
        if self.age_gate_selectors is None:
            self.age_gate_selectors = [
                "button:has-text('Yes')",
                "button:has-text('I am 21')",
                "button:has-text('Enter')",
                "[data-test='age-gate-button']",
            ]

        if self.selectors is None:
            self.selectors = {
                # Menu page selectors
                "product_card": "[data-testid='product-card'], .product-card",
                "product_link": "a[href*='/product/']",
                "product_name": "[data-testid='product-name'], .product-name",
                "product_category": "[data-testid='product-category']",
                "product_brand": "[data-testid='product-brand']",
                "product_price": "[data-testid='product-price'], .product-price",
                "product_thc": "[data-testid='product-thc'], .thc-percentage",
                "product_weight": "[data-testid='product-weight']",

                # Product detail page selectors
                "lab_results_section": "[data-test='lab-results'], .lab-results-section",
                "lab_results_button": "button:has-text('Lab Results'), button:has-text('Show More')",
                "terpene_section": "[data-testid='terps-section'], .terpene-profile",
                "total_terpenes": "[data-testid='total-terps']",
                "terpene_row": "[data-testid='terpene-row'], .terpene-item",
                "terpene_name": ".terpene-name",
                "terpene_value": ".terpene-value, .terpene-percent",

                # COA and batch selectors
                "coa_link": "a:has-text('COA'), a:has-text('Lab Results'), a:has-text('Certificate'), a[href*='.pdf']",
                "batch_info": "*:has-text('batch'), *:has-text('lot')",

                # Expandable sections
                "expandable_button": "button:has-text('Show More'), button:has-text('View Details'), [aria-expanded='false']",
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

    def get_menu_url(self, location_slug: str) -> str:
        """Get the full menu URL for a store."""
        return f"{self.base_url}{self.menu_url_pattern.format(location_slug=location_slug)}"

    def get_product_url(self, location_slug: str, product_slug: str) -> str:
        """Get the full product detail URL."""
        return f"{self.base_url}{self.product_url_pattern.format(location_slug=location_slug, product_slug=product_slug)}"

    def get_category_url(self, location_slug: str, category: str) -> str:
        """Get the category URL for a store."""
        return f"{self.base_url}{self.category_url_pattern.format(location_slug=location_slug, category=category)}"

    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        return {
            "dispensary_name": self.dispensary_name,
            "dispensary_code": self.dispensary_code,
            "grower_id": self.grower_id,
            "platform": self.platform,
            "platform_type": self.platform_type,
            "state": self.state,
            "base_url": self.base_url,
            "corporate_url": self.corporate_url,
            "retail_url": self.retail_url,
            "menu_url_pattern": self.menu_url_pattern,
            "product_url_pattern": self.product_url_pattern,
            "requires_age_gate": self.requires_age_gate,
            "requires_detail_scraping": self.requires_detail_scraping,
            "terpene_source": self.terpene_source,
            "rate_limit_ms": self.rate_limit_ms,
            "max_products_per_store": self.max_products_per_store,
            "wait_strategy": self.wait_strategy,
            "selectors": self.selectors,
            "field_mappings": self.field_mappings,
        }


# Singleton configuration instance
AYR_CONFIG = AyrConfig()


# All Florida stores (22 dispensary locations)
# Source: handoff-specifications/handoffs/HO-20260202-002.json
FL_STORES: list[StoreConfig] = [
    {"slug": "bonita-springs", "name": "Ayr - Bonita Springs", "dutchie_slug": "ayr-bonita-springs", "city": "Bonita Springs", "state": "FL"},
    {"slug": "cape-coral", "name": "Ayr - Cape Coral", "dutchie_slug": "ayr-cape-coral", "city": "Cape Coral", "state": "FL"},
    {"slug": "clearwater", "name": "Ayr - Clearwater", "dutchie_slug": "ayr-clearwater", "city": "Clearwater", "state": "FL"},
    {"slug": "fort-myers", "name": "Ayr - Fort Myers", "dutchie_slug": "ayr-fort-myers", "city": "Fort Myers", "state": "FL"},
    {"slug": "gainesville", "name": "Ayr - Gainesville", "dutchie_slug": "ayr-gainesville", "city": "Gainesville", "state": "FL"},
    {"slug": "jacksonville", "name": "Ayr - Jacksonville", "dutchie_slug": "ayr-jacksonville", "city": "Jacksonville", "state": "FL"},
    {"slug": "kissimmee", "name": "Ayr - Kissimmee", "dutchie_slug": "ayr-kissimmee", "city": "Kissimmee", "state": "FL"},
    {"slug": "lake-worth", "name": "Ayr - Lake Worth", "dutchie_slug": "ayr-lake-worth", "city": "Lake Worth", "state": "FL"},
    {"slug": "lakeland", "name": "Ayr - Lakeland", "dutchie_slug": "ayr-lakeland", "city": "Lakeland", "state": "FL"},
    {"slug": "melbourne", "name": "Ayr - Melbourne", "dutchie_slug": "ayr-melbourne", "city": "Melbourne", "state": "FL"},
    {"slug": "miami", "name": "Ayr - Miami", "dutchie_slug": "ayr-miami", "city": "Miami", "state": "FL"},
    {"slug": "miami-beach", "name": "Ayr - Miami Beach", "dutchie_slug": "ayr-miami-beach", "city": "Miami Beach", "state": "FL"},
    {"slug": "north-port", "name": "Ayr - North Port", "dutchie_slug": "ayr-north-port", "city": "North Port", "state": "FL"},
    {"slug": "ocala", "name": "Ayr - Ocala", "dutchie_slug": "ayr-ocala", "city": "Ocala", "state": "FL"},
    {"slug": "orlando", "name": "Ayr - Orlando", "dutchie_slug": "ayr-orlando", "city": "Orlando", "state": "FL"},
    {"slug": "pinellas-park", "name": "Ayr - Pinellas Park", "dutchie_slug": "ayr-pinellas-park", "city": "Pinellas Park", "state": "FL"},
    {"slug": "pompano-beach", "name": "Ayr - Pompano Beach", "dutchie_slug": "ayr-pompano-beach", "city": "Pompano Beach", "state": "FL"},
    {"slug": "port-st-lucie", "name": "Ayr - Port St. Lucie", "dutchie_slug": "ayr-port-st-lucie", "city": "Port St. Lucie", "state": "FL"},
    {"slug": "st-petersburg", "name": "Ayr - St. Petersburg", "dutchie_slug": "ayr-st-petersburg", "city": "St. Petersburg", "state": "FL"},
    {"slug": "tampa", "name": "Ayr - Tampa", "dutchie_slug": "ayr-tampa", "city": "Tampa", "state": "FL"},
    {"slug": "west-palm-beach", "name": "Ayr - West Palm Beach", "dutchie_slug": "ayr-west-palm-beach", "city": "West Palm Beach", "state": "FL"},
    {"slug": "winter-haven", "name": "Ayr - Winter Haven", "dutchie_slug": "ayr-winter-haven", "city": "Winter Haven", "state": "FL"},
]


def get_fl_stores() -> list[StoreConfig]:
    """Get all Florida Ayr store configurations."""
    return FL_STORES.copy()


def get_store_by_slug(slug: str) -> Optional[StoreConfig]:
    """Get a specific store configuration by slug."""
    for store in FL_STORES:
        if store["slug"] == slug:
            return store
    return None


def get_store_by_dutchie_slug(dutchie_slug: str) -> Optional[StoreConfig]:
    """Get a specific store configuration by Dutchie slug."""
    for store in FL_STORES:
        if store["dutchie_slug"] == dutchie_slug:
            return store
    return None


def get_stores_by_city(city: str) -> list[StoreConfig]:
    """Get all stores in a specific city."""
    city_lower = city.lower()
    return [s for s in FL_STORES if city_lower in s["city"].lower()]
