"""
Green Dragon Cannabis Company - Configuration
Platform: Squarespace (HTML scraping)
COA Portal: https://coaportal.com/greendragon
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class GreenDragonConfig:
    """Configuration for Green Dragon dispensary scraping"""
    
    # Domain and paths
    base_url: str = "https://www.greendragonfl.com"
    locations_url: str = "https://www.greendragonfl.com/locations"
    products_url: str = "https://www.greendragonfl.com/products"
    strain_guide_url: str = "https://www.greendragonfl.com/strain-guide"
    coa_portal_url: str = "https://coaportal.com/greendragon"
    
    # CSS selectors for product page
    strain_name_selector: str = ".strain-name"
    strain_dna_selector: str = ".strain-dna"
    strain_type_selector: str = ".strain-type"
    effects_selector: str = ".strain-info-content"
    
    # Scraping settings
    rate_limit_ms: int = 2000  # 2 second delay between requests
    wait_strategy: str = "domcontentloaded"  # Page load strategy
    requires_age_gate: bool = True  # Green Dragon has age gate
    
    # Request headers
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    accept_language: str = "en-US,en;q=0.9"
    
    # Pagination
    use_pagination: bool = False  # Not needed for this site
    
    # Timeout
    request_timeout_seconds: int = 30
    

@dataclass
class StoreConfig:
    """Configuration for a single Green Dragon location"""
    slug: str  # URL slug (e.g., "avon-park")
    name: str  # Display name (e.g., "Green Dragon - Avon Park")
    city: str  # City name
    url: Optional[str] = None  # Derived from slug
    
    def __post_init__(self):
        if not self.url:
            self.url = f"https://www.greendragonfl.com/{self.slug}"


# Green Dragon Florida Locations - 13 stores (as of 2026-02-02)
# Source: https://www.greendragonfl.com/locations
# Discovery: https://terprint-menu-explorer.output.samples.green-dragon
FL_STORES = [
    StoreConfig(slug="avon-park", name="Green Dragon - Avon Park", city="Avon Park"),
    StoreConfig(slug="boynton-beach", name="Green Dragon - Boynton Beach", city="Boynton Beach"),
    StoreConfig(slug="brandon", name="Green Dragon - Brandon", city="Brandon"),
    StoreConfig(slug="cape-coral", name="Green Dragon - Cape Coral", city="Cape Coral"),
    StoreConfig(slug="estero", name="Green Dragon - Estero", city="Estero"),
    StoreConfig(slug="fort-myers", name="Green Dragon - Fort Myers", city="Fort Myers"),
    StoreConfig(slug="fort-pierce", name="Green Dragon - Fort Pierce", city="Fort Pierce"),
    StoreConfig(slug="jupiter", name="Green Dragon - Jupiter", city="Jupiter"),
    StoreConfig(slug="naples", name="Green Dragon - Naples", city="Naples"),
    StoreConfig(slug="orlando", name="Green Dragon - Orlando", city="Orlando"),
    StoreConfig(slug="punta-gorda", name="Green Dragon - Punta Gorda", city="Punta Gorda"),
    StoreConfig(slug="sunrise", name="Green Dragon - Sunrise", city="Sunrise"),
    StoreConfig(slug="tampa", name="Green Dragon - Tampa", city="Tampa"),
]

# Create singleton config
GREEN_DRAGON_CONFIG = GreenDragonConfig()


def get_fl_stores() -> List[StoreConfig]:
    """Get all Florida Green Dragon stores"""
    return FL_STORES


def get_store_by_slug(slug: str) -> Optional[StoreConfig]:
    """Get a store by its URL slug"""
    for store in FL_STORES:
        if store.slug == slug:
            return store
    return None


def get_store_by_name(name: str) -> Optional[StoreConfig]:
    """Get a store by its display name"""
    for store in FL_STORES:
        if store.name == name:
            return store
    return None


def get_store_by_city(city: str) -> Optional[StoreConfig]:
    """Get store(s) by city name"""
    return [s for s in FL_STORES if s.city.lower() == city.lower()]


# Batch sizes for parallel downloads
DEFAULT_BATCH_SIZE = 3  # 3 stores per batch
DEFAULT_MAX_CONCURRENT = 2  # 2 concurrent downloads

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 1.5  # Exponential backoff
RETRY_TIMEOUT_SECONDS = 60

# COA Portal lookup strategy
COA_LOOKUP_METHOD = "batch_number"  # Look up COAs by batch number
COA_TIMEOUT_SECONDS = 30
