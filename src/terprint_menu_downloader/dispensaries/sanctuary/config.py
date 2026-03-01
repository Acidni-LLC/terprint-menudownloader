"""
Sanctuary Medicinals - Configuration
Platform: Sweed POS (HTML scraping + window.__sw JSON extraction)
Website:  https://sanctuarymed.com/shop/florida

25 Florida locations as of 2026-03-01
Discovery: HO-20260202-002 (terprint-menu-explorer)
grower_id: 9
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class SanctuaryConfig:
    """Configuration for Sanctuary Medicinals Florida scraping."""

    # Domain and paths
    base_url: str = "https://sanctuarymed.com"
    shop_base: str = "https://sanctuarymed.com/shop/florida"

    # Category paths (Sweed POS category ID in slug)
    flower_path: str = "flower-1384"
    concentrates_path: str = "concentrate-1383"
    vaporizers_path: str = "vaporizers-1386"

    # Scraping settings
    rate_limit_sec: float = 1.5       # seconds between requests
    request_timeout_sec: int = 30
    max_products_per_category: Optional[int] = None  # None = no limit

    # COA / Lab data  
    coa_link_text: str = "COA  Lab Report Link"
    lab_data_section: str = "Full lab data"

    # Platform details
    platform: str = "Sweed POS"
    platform_type: str = "html_scrape"
    grower_id: int = 9

    # Request headers
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    accept_language: str = "en-US,en;q=0.9"

    def get_menu_url(self, store_slug: str, category_path: str) -> str:
        """Build a category menu URL for a store."""
        return f"{self.shop_base}/{store_slug}/menu/{category_path}"

    def get_product_url(self, store_slug: str, product_slug: str) -> str:
        """Build a product detail URL for a store."""
        return f"{self.shop_base}/{store_slug}/product/{product_slug}"


@dataclass
class SanctuaryStore:
    """A single Sanctuary Florida location."""
    slug: str          # URL slug (e.g., "orlando")
    name: str          # Display name (e.g., "Sanctuary - Orlando I Drive")
    city: str          # City name
    state: str = "FL"


# ---------------------------------------------------------------------------
# Florida Locations — 25 stores (HO-20260202-002)
# URL template: https://sanctuarymed.com/shop/florida/{slug}/menu
# ---------------------------------------------------------------------------
FL_STORES: List[SanctuaryStore] = [
    SanctuaryStore(slug="bocapalmetto",         name="Sanctuary - Boca Raton Palmetto",       city="Boca Raton"),
    SanctuaryStore(slug="bocapowerline",         name="Sanctuary - Boca Raton Powerline",      city="Boca Raton"),
    SanctuaryStore(slug="boyntonbeach",          name="Sanctuary - Boynton Beach",             city="Boynton Beach"),
    SanctuaryStore(slug="clearwater",            name="Sanctuary - Clearwater",                city="Clearwater"),
    SanctuaryStore(slug="daytona",               name="Sanctuary - Daytona",                   city="Daytona Beach"),
    SanctuaryStore(slug="delraybeach",           name="Sanctuary - Delray Beach",              city="Delray Beach"),
    SanctuaryStore(slug="dunedin",               name="Sanctuary - Dunedin",                   city="Dunedin"),
    SanctuaryStore(slug="ftpierce",              name="Sanctuary - Fort Pierce",               city="Fort Pierce"),
    SanctuaryStore(slug="gainesville",           name="Sanctuary - Gainesville",               city="Gainesville"),
    SanctuaryStore(slug="greenacres",            name="Sanctuary - Greenacres",                city="Greenacres"),
    SanctuaryStore(slug="hallandalebeach",       name="Sanctuary - Hallandale Beach",          city="Hallandale Beach"),
    SanctuaryStore(slug="jacksonvillebeach",     name="Sanctuary - Jacksonville Beach Blvd",  city="Jacksonville"),
    SanctuaryStore(slug="jacksonvilleedgewood",  name="Sanctuary - Jacksonville Edgewood",    city="Jacksonville"),
    SanctuaryStore(slug="jupiter",               name="Sanctuary - Jupiter",                   city="Jupiter"),
    SanctuaryStore(slug="marianna",              name="Sanctuary - Marianna",                  city="Marianna"),
    SanctuaryStore(slug="miami",                 name="Sanctuary - Miami",                     city="Miami"),
    SanctuaryStore(slug="orlandoIdrive",         name="Sanctuary - Orlando I Drive",           city="Orlando"),
    SanctuaryStore(slug="orlandoleevista",       name="Sanctuary - Orlando Lee Vista",         city="Orlando"),
    SanctuaryStore(slug="palatka",               name="Sanctuary - Palatka",                   city="Palatka"),
    SanctuaryStore(slug="sarasota",              name="Sanctuary - Sarasota",                  city="Sarasota"),
    SanctuaryStore(slug="sebring",               name="Sanctuary - Sebring",                   city="Sebring"),
    SanctuaryStore(slug="stpetersburg",          name="Sanctuary - St. Petersburg",            city="St. Petersburg"),
    SanctuaryStore(slug="tampa",                 name="Sanctuary - Tampa Waters",              city="Tampa"),
    SanctuaryStore(slug="TampaMidtown",          name="Sanctuary - Tampa Midtown",             city="Tampa"),
    SanctuaryStore(slug="westpalmbeachokeechobee", name="Sanctuary - West Palm Beach",          city="West Palm Beach"),
]

# Category slugs scraped on every run
FL_CATEGORIES: Dict[str, str] = {
    "flower":       "flower-1384",
    "concentrates": "concentrate-1383",
    "vaporizers":   "vaporizers-1386",
}

# Singleton config
SANCTUARY_CONFIG = SanctuaryConfig()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def get_fl_stores() -> List[SanctuaryStore]:
    """Return all Florida Sanctuary stores."""
    return FL_STORES


def get_store_by_slug(slug: str) -> Optional[SanctuaryStore]:
    return next((s for s in FL_STORES if s.slug == slug), None)


def get_store_by_name(name: str) -> Optional[SanctuaryStore]:
    return next((s for s in FL_STORES if s.name == name), None)


def get_store_by_city(city: str) -> List[SanctuaryStore]:
    return [s for s in FL_STORES if s.city.lower() == city.lower()]
