# Curaleaf FL Configuration for terprint-config

## Overview

Configuration and scraping module for Curaleaf Florida dispensary menus.

| Attribute | Value |
|-----------|-------|
| **Dispensary** | Curaleaf |
| **State** | Florida |
| **Platform** | SweedPOS |
| **Scrape Type** | HTML |
| **Store Count** | 65 dispensaries |
| **Terpene Coverage** | ~85% |
| **Discovery Date** | December 2025 |

## Quick Start

```python
from terprint_config.dispensaries.curaleaf import CuraleafScraper, FL_STORES, CURALEAF_CONFIG

# Get all FL stores
stores = FL_STORES
print(f"Found {len(stores)} FL stores")

# Scrape a single store with terpenes
with CuraleafScraper() as scraper:
    products = scraper.scrape_store_menu_with_terpenes(
        "curaleaf-dispensary-tampa",
        sample_terpenes=10  # Only fetch terpenes for first 10 products
    )
    print(f"Downloaded {len(products)} products")
```

## Configuration

### CuraleafConfig Properties

```python
CURALEAF_CONFIG.base_url           # "https://curaleaf.com"
CURALEAF_CONFIG.menu_url_pattern   # "/shop/{store_slug}"
CURALEAF_CONFIG.product_url_pattern # "/shop/{store_slug}/product/{product_slug}"
CURALEAF_CONFIG.rate_limit_ms      # 500 (milliseconds between detail requests)
CURALEAF_CONFIG.requires_detail_scraping  # True
```

### URL Generation

```python
# Menu page URL
menu_url = CURALEAF_CONFIG.get_menu_url("curaleaf-dispensary-tampa")
# -> "https://curaleaf.com/shop/curaleaf-dispensary-tampa"

# Product detail URL
product_url = CURALEAF_CONFIG.get_product_url("curaleaf-dispensary-tampa", "baya-dulce")
# -> "https://curaleaf.com/shop/curaleaf-dispensary-tampa/product/baya-dulce"
```

## Scraping Architecture

### Two-Level Scraping (Required for Terpenes)

```
Level 1: Menu Page (/shop/{store_slug})
├── Product cards with: name, category, brand, price, THC%, weight
└── Product URLs for detail pages

Level 2: Product Detail Page (/shop/{store_slug}/product/{product_slug})
├── Total terpenes percentage
├── Individual terpene breakdown (Limonene, Myrcene, etc.)
└── Lab test URL (yourcoa.com COA link)
```

### Rate Limiting

**IMPORTANT:** Respect rate limits to avoid blocking.

```python
CURALEAF_CONFIG.rate_limit_ms = 500  # 0.5 seconds between detail requests
```

## Menu Downloader Integration

### Blob Storage Path Pattern

```
dispensaries/curaleaf/{year}/{month}/{day}/{timestamp}.json
```

### Output Format

```json
{
  "dispensary": "curaleaf",
  "store_slug": "curaleaf-dispensary-tampa",
  "store_name": "Tampa",
  "state": "FL",
  "timestamp": "2025-12-16T12:00:00Z",
  "product_count": 92,
  "products": [
    {
      "name": "Baya Dulce Whole Flower",
      "category": "Flower",
      "brand": "Curaleaf",
      "price": "$40.00",
      "thc_percent": 29.9,
      "weight": "3.5g",
      "total_terpenes_percent": 1.77,
      "top_terpenes": [
        {"name": "Limonene", "percent": 0.65},
        {"name": "Caryophyllene", "percent": 0.45},
        {"name": "Myrcene", "percent": 0.32}
      ],
      "lab_test_url": "https://yourcoa.com/certificate/pdf/..."
    }
  ],
  "metadata": {
    "platform": "SweedPOS",
    "scrape_type": "html",
    "terpene_source": "product_detail_page"
  }
}
```

## Field Mappings

| Source Field | terprint Schema | Notes |
|--------------|-----------------|-------|
| `name` | `product_name` | Product display name |
| `category` | `product_category` | Flower, Vape, Edible, etc. |
| `brand` | `product_brand` | Curaleaf, Select, etc. |
| `thc_percent` | `thc_percent` | Parsed from text |
| `total_terpenes_percent` | `total_terpenes` | From detail page |
| `top_terpenes` | `terpene_profile` | Array of {name, percent} |
| `lab_test_url` | `coa_url` | yourcoa.com link |

## Store List

All 65 FL stores are available in `FL_STORES`:

```python
from terprint_config.dispensaries.curaleaf import FL_STORES, get_store_by_slug, get_stores_by_city

# Get specific store
tampa = get_store_by_slug("curaleaf-dispensary-tampa")

# Get all stores in a city
jax_stores = get_stores_by_city("Jacksonville")
```

## Testing

```python
# Validate scraper works
with CuraleafScraper() as scraper:
    # Quick test - menu only (no terpenes)
    products = scraper.scrape_menu_page("curaleaf-dispensary-cape-canaveral")
    assert len(products) > 0
    
    # Full test with terpenes (sample 5)
    products = scraper.scrape_store_menu_with_terpenes(
        "curaleaf-dispensary-cape-canaveral",
        sample_terpenes=5
    )
    terpene_count = sum(1 for p in products if p.get('total_terpenes_percent'))
    print(f"Terpene coverage: {terpene_count}/{len(products)}")
```

## Notes

- **Delivery stores** (slug contains "delivery") return 0 products - these are routing entries only
- **The Hemp Company** store is a CBD-only location
- **Lab URLs** use yourcoa.com COA service
- **Product availability** varies by store (90-100 products typical)
