"""
Green Dragon Cannabis Company - Configuration
Platform: Sweed POS (HTML scraping + window.__sw JSON extraction)
Website:  https://shop.greendragon.com

17 verified Florida locations as of 2026-03-01
(13 more exist on greendragonfl.com but redirect to CO on Sweed POS)
Discovery: green_dragon_prototype_v2.py --validate-slugs
grower_id: 3
"""

from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class GreenDragonConfig:
    """Configuration for Green Dragon FL dispensary scraping."""

    # Domain and paths — Sweed POS is the data source
    base_url: str = "https://shop.greendragon.com"
    # Legacy Squarespace site — has locations info but NO product data
    legacy_url: str = "https://www.greendragonfl.com"
    coa_portal_url: str = "https://coaportal.com/greendragon"

    # Category paths (FL category IDs — different from CO!)
    flower_path: str = "flower-142"
    concentrates_path: str = "concentrates-517"
    vaporizers_path: str = "vaporizers-519"

    # Scraping settings
    rate_limit_sec: float = 1.5       # seconds between requests
    request_timeout_sec: int = 30
    max_products_per_category: Optional[int] = None  # None = no limit

    # Platform details
    platform: str = "Sweed POS"
    platform_type: str = "html_scrape"
    grower_id: int = 3

    # COA / Lab data source
    # Green Dragon COAs are hosted on LabDrive (Method Testing Labs)
    # URL is in the product variant's labTests.fullLabDataUrl field
    coa_host: str = "mete.labdrive.net"

    # Request headers
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    accept_language: str = "en-US,en;q=0.9"

    def get_menu_url(self, store_slug: str, category_path: str) -> str:
        """Build a category menu URL for a store."""
        return f"{self.base_url}/{store_slug}/menu/{category_path}"

    def get_product_url(self, store_slug: str, category_path: str, product_slug: str) -> str:
        """Build a product detail URL for a store."""
        return f"{self.base_url}/{store_slug}/menu/{category_path}/{product_slug}"


@dataclass
class StoreConfig:
    """A single Green Dragon Florida location."""
    slug: str           # Sweed POS slug (e.g., "avon")
    name: str           # Display name (e.g., "Green Dragon - Avon Park")
    city: str           # City name
    gd_slug: str = ""   # greendragonfl.com slug (may differ from Sweed slug)
    state: str = "FL"
    url: Optional[str] = None

    def __post_init__(self):
        if not self.url:
            self.url = f"https://shop.greendragon.com/{self.slug}/menu"


# ---------------------------------------------------------------------------
# Florida Locations — 17 verified on Sweed POS (2026-03-01)
# slug = Sweed POS slug, gd_slug = greendragonfl.com slug
# Validated by: green_dragon_prototype_v2.py --validate-slugs
#
# 13 additional stores exist on greendragonfl.com but redirect to
# ft-collins-rec (Colorado) on Sweed POS — not yet online for ordering.
# ---------------------------------------------------------------------------
FL_STORES: List[StoreConfig] = [
    StoreConfig(slug="avon",               name="Green Dragon - Avon Park",          city="Avon Park",          gd_slug="avon-park"),
    StoreConfig(slug="boynton-beach-east",  name="Green Dragon - Boynton Beach East", city="Boynton Beach",      gd_slug="boynton-beach-east"),
    StoreConfig(slug="boynton-beach-west",  name="Green Dragon - Boynton Beach West", city="Boynton Beach",      gd_slug="boynton-beach-west"),
    StoreConfig(slug="brooksville",         name="Green Dragon - Brooksville",        city="Brooksville",        gd_slug="brooksville"),
    StoreConfig(slug="cape-coral",          name="Green Dragon - Cape Coral",         city="Cape Coral",         gd_slug="cape-coral"),
    StoreConfig(slug="coconut-creek",       name="Green Dragon - Coconut Creek",      city="Coconut Creek",      gd_slug="coconut-creek"),
    StoreConfig(slug="crescent-city",       name="Green Dragon - Crescent City",      city="Crescent City",      gd_slug="crescent-city"),
    StoreConfig(slug="crystal-river",       name="Green Dragon - Crystal River",      city="Crystal River",      gd_slug="crystal-river"),
    StoreConfig(slug="englewood",           name="Green Dragon - Englewood",          city="Englewood",          gd_slug="englewood"),
    StoreConfig(slug="ft-pierce",           name="Green Dragon - Fort Pierce",        city="Fort Pierce",        gd_slug="fort-pierce"),
    StoreConfig(slug="holly-hill",          name="Green Dragon - Holly Hill",         city="Holly Hill",         gd_slug="holly-hill"),
    StoreConfig(slug="inverness",           name="Green Dragon - Inverness",          city="Inverness",          gd_slug="inverness"),
    StoreConfig(slug="lake-worth",          name="Green Dragon - Lake Worth",         city="Lake Worth",         gd_slug="lake-worth"),
    StoreConfig(slug="ocala",               name="Green Dragon - Ocala",              city="Ocala",              gd_slug="ocala"),
    StoreConfig(slug="orlando",             name="Green Dragon - Orlando",            city="Orlando",            gd_slug="orlando"),
    StoreConfig(slug="tampa",               name="Green Dragon - Tampa",              city="Tampa",              gd_slug="tampa"),
    StoreConfig(slug="west-palm",           name="Green Dragon - West Palm Beach",    city="West Palm Beach",    gd_slug="west-palm-beach"),
]

# Category slugs scraped on every run
FL_CATEGORIES: Dict[str, str] = {
    "flower":       "flower-142",
    "concentrates": "concentrates-517",
    "vaporizers":   "vaporizers-519",
}

# Singleton config
GREEN_DRAGON_CONFIG = GreenDragonConfig()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_fl_stores() -> List[StoreConfig]:
    """Return all verified Florida Green Dragon stores."""
    return FL_STORES


def get_store_by_slug(slug: str) -> Optional[StoreConfig]:
    """Get a store by its Sweed POS slug."""
    return next((s for s in FL_STORES if s.slug == slug), None)


def get_store_by_gd_slug(slug: str) -> Optional[StoreConfig]:
    """Get a store by its greendragonfl.com slug."""
    return next((s for s in FL_STORES if s.gd_slug == slug), None)


def get_store_by_name(name: str) -> Optional[StoreConfig]:
    """Get a store by its display name."""
    return next((s for s in FL_STORES if s.name == name), None)


def get_store_by_city(city: str) -> List[StoreConfig]:
    """Get all stores in a specific city."""
    return [s for s in FL_STORES if s.city.lower() == city.lower()]
