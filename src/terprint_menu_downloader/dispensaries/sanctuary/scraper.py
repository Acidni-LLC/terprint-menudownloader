"""
Sanctuary Medicinals - Sweed POS Menu Scraper
==============================================
Platform  : Sweed POS  (sanctuarymed.com/shop/florida)
Data Layer: window.__sw JSON blob + HTML fallbacks
Lab Data  : Full terpene table + COA PDF link on product detail pages

Pipeline per store:
  1. Fetch category menu page  → extract product links via <a href>
  2. Fetch each product page   → extract window.__sw JSON blob
  3. Normalize into standard product dict
  4. Return list of products with potency, terpenes, COA URL, batch ID

Usage (standalone test):
    python scraper.py --store orlando --category flower --limit 3
"""

import httpx
import re
import json
import time
import logging
import argparse
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from bs4 import BeautifulSoup

try:
    from .config import SANCTUARY_CONFIG, SanctuaryConfig, SanctuaryStore, FL_CATEGORIES
except ImportError:
    from config import SANCTUARY_CONFIG, SanctuaryConfig, SanctuaryStore, FL_CATEGORIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


def _get(client: httpx.Client, url: str, rate_limit: float = 1.5) -> Optional[str]:
    """Fetch a URL, rate-limit before the request, return HTML or None."""
    time.sleep(rate_limit)
    try:
        resp = client.get(url, headers=_DEFAULT_HEADERS, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} → {url}")
    except Exception as e:
        logger.warning(f"Request failed [{url}]: {e}")
    return None


# ---------------------------------------------------------------------------
# Layer 1: Menu listing — extract product links
# ---------------------------------------------------------------------------

def scrape_menu_links(
    client: httpx.Client,
    store_slug: str,
    category: str,
    category_path: str,
    config: SanctuaryConfig = None,
) -> List[Dict[str, Any]]:
    """
    Fetch a Sweed POS category menu page and extract product links.

    The menu page href pattern for Sanctuary is:
        /shop/florida/{store}/product/{product-slug}
    OR the Sweed category-scoped path:
        /shop/florida/{store}/menu/{category}-{id}/{product-slug}

    Returns list of dicts with: product_slug, product_url, category, sweed_product_id
    """
    config = config or SANCTUARY_CONFIG
    url = config.get_menu_url(store_slug, category_path)
    logger.info(f"  [{category}] Fetching menu: {url}")

    html = _get(client, url, config.rate_limit_sec)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    products: List[Dict[str, Any]] = []
    seen: set = set()

    # Patterns that match Sweed POS product links on sanctuarymed.com
    shop_prefix = f"/shop/florida/{store_slug}/"

    for a in soup.find_all("a", href=True):
        href: str = a["href"]

        # Must be a product link for this store
        if not href.startswith(shop_prefix) and not href.startswith(f"https://sanctuarymed.com/shop/florida/{store_slug}/"):
            continue

        # Normalise to path only
        path = href.replace(f"https://sanctuarymed.com", "")

        # Must reference either /product/ or a specific category menu item
        # Valid: /product/{slug}  or  /menu/{category-id}/{slug}
        # Invalid: /menu  /menu/discounts  /about-us ...
        if "/product/" not in path:
            # For menu paths, require it's under a category sub-path (2+ segments after /menu/)
            menu_idx = path.find("/menu/")
            if menu_idx == -1:
                continue
            after_menu = path[menu_idx + len("/menu/"):]
            # Must have at least one / after the category (i.e., /menu/{cat}/{slug})
            if "/" not in after_menu:
                continue

        # Derive product slug (last path segment, strip query string)
        product_slug = path.split("/")[-1].split("?")[0].rstrip("/")
        if not product_slug or product_slug in seen:
            continue
        seen.add(product_slug)

        # Build absolute product detail URL — preserve the exact href Sweed gave us
        # (Sanctuary uses /menu/{category}/{slug}, NOT /product/{slug})
        if href.startswith("http"):
            product_url = path  # already absolute, strip domain
            product_url = f"https://sanctuarymed.com{product_url}" if product_url.startswith("/") else href
        else:
            # Strip query string for cleaner URL but keep the full path
            clean_path = path.split("?")[0]
            product_url = f"https://sanctuarymed.com{clean_path}"

        # Extract Sweed numeric product ID from end of slug (e.g., blue-dream-440419)
        id_match = re.search(r"-(\d+)$", product_slug)
        sweed_id = id_match.group(1) if id_match else None

        products.append({
            "product_slug":     product_slug,
            "product_url":      product_url,
            "category":         category,
            "sweed_product_id": sweed_id,
        })

    logger.info(f"  [{category}] Found {len(products)} product links")
    return products


# ---------------------------------------------------------------------------
# Layer 2: Product detail — window.__sw JSON extraction
# ---------------------------------------------------------------------------

def scrape_product_detail(
    client: httpx.Client,
    product: Dict[str, Any],
    config: SanctuaryConfig = None,
) -> Dict[str, Any]:
    """
    Fetch a Sanctuary product detail page and extract full lab data
    from the window.__sw JSON blob embedded in the page.

    Adds to the product dict:
        name, brand, strain_name, strain_type,
        thc_percent, cbd_percent,
        terpenes {name: value%},
        flavors, effects,
        coa_url, batch_id,
        category_name, subcategory, price, weight,
        detail_source (window.__sw | html_fallback | none)
    """
    config = config or SANCTUARY_CONFIG
    url = product.get("product_url", "")
    if not url:
        return product

    html = _get(client, url, config.rate_limit_sec)
    if not html:
        product["detail_error"] = "fetch_failed"
        return product

    # Primary: window.__sw JSON blob
    sw_data = _extract_from_sw_blob(html, product.get("sweed_product_id"))
    if sw_data:
        product.update(sw_data)
        product["detail_source"] = "window.__sw"
    else:
        # Fallback: plain HTML parsing
        html_data = _extract_from_html(html)
        if html_data:
            product.update(html_data)
            product["detail_source"] = "html_fallback"
        else:
            product["detail_source"] = "none"

    product["detail_scraped_at"] = datetime.now(timezone.utc).isoformat()
    return product


# ---- window.__sw extraction (Sweed POS standard) ----

# ---- window.__sw_qc extraction (Sweed POS — Sanctuary) ----

def _extract_from_sw_blob(html: str, variant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Extract product object from window.__sw_qc (React Query cache injected by Sweed POS).

    Actual Sanctuary data structure (verified Jan 2026):
      window.__sw_qc = {
        "queries": [
          {
            "queryHash": '[\"/Products/GetProductByVariantId\",{\"variantId\":\"164618\"}]',
            "state": {
              "data": {
                "id": 119920,
                "name": "Wedding Mints",
                "strain":   {"name": "...", "prevalence": {"name": "Indica"}, "terpenes": []},
                "brand":    {"name": "Sanctuary Cannabis"},
                "category": {"name": "Flower"},
                "variants": [{
                  "id": 164618,
                  "labTests": {
                    "thc": {"value": [29.5], "unitAbbr": "%"},
                    "cbd": {"value": [0.0456], "unitAbbr": "%"},
                    "fullLabDataUrl": "https://s3...."
                  },
                  "price": 50,
                  "unitSize": {"value": 3.5, "unitAbbr": "G"}
                }]
              }
            }
          }
        ]
      }
    """
    # Sanctuary uses window.__sw_qc for the React Query cache
    m = re.search(r"window\.__sw_qc\s*=\s*(\{)", html)
    if not m:
        # Fallback: try legacy window.__sw with dehydratedState
        m = re.search(r"window\.__sw\s*=\s*(\{)", html)
        if not m:
            return None
        var = "window.__sw"
    else:
        var = "window.__sw_qc"

    start = m.start(1)
    raw = html[start:]
    depth = 0
    end = 0
    for i, ch in enumerate(raw):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0 and i > 0:
            end = i + 1
            break

    if not end:
        return None

    try:
        qc_data = json.loads(raw[:end])
    except json.JSONDecodeError as e:
        logger.debug(f"JSON decode error in {var}: {e}")
        return None

    # Support both structures
    if var == "window.__sw_qc":
        queries = qc_data.get("queries", [])
    else:
        queries = qc_data.get("dehydratedState", {}).get("queries", [])

    for q in queries:
        qhash = q.get("queryHash", "")
        if "GetProductByVariantId" not in qhash:
            continue
        product_data = q.get("state", {}).get("data")
        if product_data and isinstance(product_data, dict):
            return _normalize_sw_product(product_data)

    return None


def _try_partial_parse(s: str) -> Optional[Dict]:
    """Last-resort: try to salvage a truncated JSON object."""
    for i in range(len(s), 0, -100):
        try:
            return json.loads(s[:i] + "}" * s[:i].count("{") - s[:i].count("}") * "}")
        except Exception:
            continue
    return None


def _normalize_sw_product(data: Dict) -> Dict[str, Any]:
    """Normalize Sweed POS product JSON (GetProductByVariantId) into Terprint standard format.

    Verified structure (Sanctuary, Jan 2026):
      data.name, data.id
      data.brand.name
      data.strain.name, .prevalence.name, .terpenes (always [] for Sanctuary)
      data.category.name, data.subcategory.name
      data.effects[]
      data.variants[0].labTests.thc.value[0]  — THC%
      data.variants[0].labTests.cbd.value[0]  — CBD%
      data.variants[0].labTests.fullLabDataUrl — COA PDF URL
      data.variants[0].id                     — variant/batch ID
      data.variants[0].price
      data.variants[0].unitSize.value + .unitAbbr
    """
    result: Dict[str, Any] = {}

    # Core identification
    result["name"]             = data.get("name", "").strip()
    result["sweed_product_id"] = str(data.get("id", ""))

    # Brand
    brand = data.get("brand")
    if isinstance(brand, dict):
        result["brand"]    = brand.get("name", "").strip()
        result["brand_id"] = brand.get("id")

    # Strain / genetics
    strain = data.get("strain")
    if isinstance(strain, dict):
        result["strain_name"] = strain.get("name", "").strip()
        prevalence = strain.get("prevalence")
        if isinstance(prevalence, dict):
            result["strain_type"] = prevalence.get("name", "")  # Indica/Sativa/Hybrid
        # Sweed POS stores terpenes on strain — usually empty for Sanctuary
        terps = strain.get("terpenes") or []
        if terps:
            result["terpenes"] = {
                t.get("name", f"terp_{i}"): float(t.get("value", 0))
                for i, t in enumerate(terps) if isinstance(t, dict)
            }

    # Category / subcategory
    cat = data.get("category")
    if isinstance(cat, dict):
        result["category_name"] = cat.get("name", "")

    subcat = data.get("subcategory")
    if isinstance(subcat, dict):
        result["subcategory"] = subcat.get("name", "")

    # Effects
    effects = data.get("effects") or []
    if effects:
        result["effects"] = [
            e.get("name", str(e)) if isinstance(e, dict) else str(e)
            for e in effects
        ]

    # Description
    desc = data.get("description") or data.get("longDescription")
    if desc:
        result["description"] = desc

    # Images
    images = data.get("images") or []
    if images:
        img0 = images[0]
        if isinstance(img0, str):
            result["image_url"] = img0
        elif isinstance(img0, dict):
            result["image_url"] = img0.get("url") or img0.get("src")

    # ---- Variants — take first variant for lab data, price, weight ----
    variants = data.get("variants") or []
    variant = variants[0] if variants else {}

    # Variant / batch ID (the numeric part at end of URL slug)
    v_id = variant.get("id")
    if v_id:
        result["variant_id"] = str(v_id)

    # Lab tests (Sanctuary-specific structure)
    lab = variant.get("labTests") or {}

    # THC: labTests.thc.value = [29.5]
    thc_obj = lab.get("thc")
    if isinstance(thc_obj, dict):
        thc_vals = thc_obj.get("value") or []
        if thc_vals:
            try:
                result["thc_percent"] = float(thc_vals[0])
            except (TypeError, ValueError):
                pass

    # CBD: labTests.cbd.value = [0.0456]
    cbd_obj = lab.get("cbd")
    if isinstance(cbd_obj, dict):
        cbd_vals = cbd_obj.get("value") or []
        if cbd_vals:
            try:
                result["cbd_percent"] = float(cbd_vals[0])
            except (TypeError, ValueError):
                pass

    # COA URL: labTests.fullLabDataUrl (S3 presigned URL from Confident Cannabis)
    coa_url = lab.get("fullLabDataUrl")
    if coa_url and isinstance(coa_url, str) and coa_url.startswith("http"):
        result["coa_url"] = coa_url

    # Fallback: also check top-level or other variant keys
    if "coa_url" not in result:
        for key in ("fullLabDataUrl", "labDataUrl", "coaUrl"):
            v2 = data.get(key) or variant.get(key)
            if v2 and isinstance(v2, str) and v2.startswith("http"):
                result["coa_url"] = v2
                break

    # Price
    price = variant.get("price") or variant.get("priceRec")
    if price is not None:
        try:
            result["price"] = float(price)
        except (TypeError, ValueError):
            pass

    # Weight (unitSize)
    unit_size = variant.get("unitSize") or {}
    if isinstance(unit_size, dict):
        w_val = unit_size.get("value")
        w_abbr = unit_size.get("unitAbbr", "")
        if w_val is not None:
            result["weight"] = f"{w_val}{w_abbr}".strip()

    return result


# ---- HTML fallback (when window.__sw is absent) ----

def _extract_from_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Fallback: parse the rendered HTML of a Sanctuary product page.

    Sanctuary uses Sweed POS React with CSS modules — the lab data section
    renders label/value pairs using two sibling divs:
      <div class="OUIWQpt">Total THC</div>
      <div class="zRYKXNN">29.5%</div>

    NOTE: Individual terpene names are NOT present in the Sanctuary HTML;
    only "Total Terpenes %" is shown.  Individual terpene data requires the
    Confident Cannabis COA PDF.
    """
    result: Dict[str, Any] = {}
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = soup.find("h1") or soup.find("h2")
    if title:
        result["name"] = title.get_text(strip=True)

    # ---- Lab data via CSS classes OUIWQpt (label) + zRYKXNN (value) ----
    # These are Sweed POS CSS-module class names observed on Sanctuary product pages.
    # Walk every label element and pair it with its sibling/neighbor value element.
    def _find_value_el(label_el):
        """Return the zRYKXNN value element adjacent to a label element."""
        # Try immediate next sibling first (most common layout)
        sibling = label_el.find_next_sibling()
        if sibling and "zRYKXNN" in sibling.get("class", []):
            return sibling
        # Try parent's child search
        parent = label_el.parent
        if parent:
            val = parent.find(class_="zRYKXNN")
            if val:
                return val
        return None

    for label_el in soup.find_all(class_="OUIWQpt"):
        label_text = label_el.get_text(strip=True).lower()
        val_el = _find_value_el(label_el)
        if val_el is None:
            continue
        val_text = val_el.get_text(strip=True)

        if "total thc" in label_text:
            m = re.search(r"([0-9]+\.?[0-9]*)", val_text)
            if m:
                result["thc_percent"] = float(m.group(1))
        elif "total cbd" in label_text:
            m = re.search(r"([0-9]+\.?[0-9]*)", val_text)
            if m:
                result["cbd_percent"] = float(m.group(1))
        elif "total terpenes" in label_text:
            m = re.search(r"([0-9]+\.?[0-9]*)", val_text)
            if m:
                result["total_terpenes_pct"] = float(m.group(1))
        elif "strain prevalence" in label_text:
            # Value is like "#Indica" or "Indica"
            result["strain_type"] = val_text.lstrip("#").strip()
        elif label_text == "strain":
            result["strain_name"] = val_text.lstrip("#").strip()

    # ---- Regex fallback for THC/CBD if CSS classes not found ----
    # Sanctuary renders "Total THC29.5%" in some contexts (label/value sibling
    # text gets concatenated).  The regex below handles both:
    #   "Total THC 29.5%" and "Total THC29.5%"
    if "thc_percent" not in result:
        thc_m = re.search(r"Total\s*THC\s*([0-9]+\.?[0-9]*)\s*%", html, re.IGNORECASE)
        if thc_m:
            result["thc_percent"] = float(thc_m.group(1))

    if "cbd_percent" not in result:
        cbd_m = re.search(r"Total\s*CBD\s*([0-9]+\.?[0-9]*)\s*%", html, re.IGNORECASE)
        if cbd_m:
            result["cbd_percent"] = float(cbd_m.group(1))

    # ---- COA URL — S3 URL or anchor with "COA" / "Lab Report" text ----
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        href = a["href"]
        if (
            "coa" in text
            or "lab report" in text
            or "certificate" in text
            or href.endswith(".pdf")
            or "confidentcannabis.com" in href
            or "s3.us-west" in href
        ):
            if href.startswith("http"):
                result["coa_url"] = href
                break
            elif href.startswith("/"):
                result["coa_url"] = f"https://sanctuarymed.com{href}"
                break

    return result if result.get("name") or result.get("thc_percent") else None


# ---------------------------------------------------------------------------
# High-level: scrape a full store
# ---------------------------------------------------------------------------

class SanctuaryStoreScraper:
    """
    Scrapes all products for a single Sanctuary Florida store.

    Usage:
        scraper = SanctuaryStoreScraper()
        result  = scraper.scrape_store("orlando")
    """

    def __init__(self, config: SanctuaryConfig = None):
        self.config = config or SANCTUARY_CONFIG

    def scrape_store(
        self,
        store: SanctuaryStore,
        categories: Optional[Dict[str, str]] = None,
        include_details: bool = True,
        max_products: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Scrape all categories for one store.

        Returns:
            {
                "dispensary":     "sanctuary",
                "store_slug":     ...,
                "store_name":     ...,
                "state":          "FL",
                "products":       [...],
                "product_count":  N,
                "timestamp":      ISO-8601,
                "metadata":       {...},
            }
        """
        categories = categories or FL_CATEGORIES
        all_products: List[Dict[str, Any]] = []

        with httpx.Client(follow_redirects=True, timeout=self.config.request_timeout_sec) as client:
            for category_name, category_path in categories.items():
                logger.info(f"Store [{store.slug}] - category: {category_name}")
                products = scrape_menu_links(
                    client, store.slug, category_name, category_path, self.config
                )

                if include_details:
                    for i, p in enumerate(products):
                        if max_products and len(all_products) + i >= max_products:
                            break
                        logger.info(
                            f"  [{category_name}] Detail {i+1}/{len(products)}: "
                            f"{p.get('product_slug', '?')}"
                        )
                        scrape_product_detail(client, p, self.config)

                all_products.extend(products)

                if max_products and len(all_products) >= max_products:
                    logger.info(f"  Reached max_products={max_products}, stopping.")
                    break

        return {
            "dispensary":    "sanctuary",
            "store_slug":    store.slug,
            "store_name":    store.name,
            "city":          store.city,
            "state":         store.state,
            "products":      all_products,
            "product_count": len(all_products),
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "platform":           self.config.platform,
                "platform_type":      self.config.platform_type,
                "grower_id":          self.config.grower_id,
                "categories_scraped": list(categories.keys()),
                "include_details":    include_details,
                "scraper_version":    "1.0",
            },
        }


# ---------------------------------------------------------------------------
# Standalone smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Sanctuary scraper smoke test")
    parser.add_argument("--store",    default="orlando",  help="Store slug (default: orlando)")
    parser.add_argument("--category", default="flower",   help="Category (default: flower)")
    parser.add_argument("--limit",    type=int, default=3, help="Max products (default: 3)")
    parser.add_argument("--no-details", action="store_true", help="Skip product detail pages")
    args = parser.parse_args()

    try:
        from config import SANCTUARY_CONFIG, FL_STORES, FL_CATEGORIES
        from config import get_store_by_slug
    except ImportError:
        from terprint_menu_downloader.dispensaries.sanctuary.config import (
            SANCTUARY_CONFIG, FL_STORES, FL_CATEGORIES, get_store_by_slug
        )

    store = get_store_by_slug(args.store)
    if not store:
        print(f"Unknown store slug: {args.store}")
        print(f"Available: {[s.slug for s in FL_STORES]}")
        sys.exit(1)

    categories = {args.category: FL_CATEGORIES[args.category]} if args.category in FL_CATEGORIES else FL_CATEGORIES

    scraper = SanctuaryStoreScraper()
    result  = scraper.scrape_store(
        store,
        categories=categories,
        include_details=not args.no_details,
        max_products=args.limit,
    )

    print(f"\n=== {result['store_name']} ===")
    print(f"Products: {result['product_count']}")
    for p in result["products"][:args.limit]:
        thc   = p.get("thc_percent")
        terps = list(p.get("terpenes", {}).keys())[:3]
        coa   = "✓ COA" if p.get("coa_url") else "✗ no COA"
        print(f"  {p.get('name','?')}  THC={thc}%  terpenes={terps}  {coa}")
