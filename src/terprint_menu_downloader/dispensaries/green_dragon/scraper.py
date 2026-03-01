"""
Green Dragon Cannabis Company - Sweed POS Menu Scraper
======================================================
Platform  : Sweed POS  (shop.greendragon.com)
Data Layer: window.__sw JSON blob + HTML fallbacks
Lab Data  : Full lab tests + COA PDF from LabDrive (mete.labdrive.net)

Pipeline per store:
  1. Fetch category menu page  → extract product links via <a href>
  2. Fetch each product page   → extract window.__sw JSON blob
  3. Normalize into standard product dict
  4. Return list of products with potency, terpenes, COA URL, batch ID

NOTE: Green Dragon uses ``window.__sw`` with ``dehydratedState.queries``
      (Sanctuary uses ``window.__sw_qc`` with a flat ``queries`` array).

Usage (standalone test):
    python scraper.py --store avon --category flower --limit 3
"""

import httpx
import re
import json
import os
import time
import logging
import argparse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup

try:
    from .config import GREEN_DRAGON_CONFIG, GreenDragonConfig, StoreConfig, FL_CATEGORIES
except ImportError:
    from config import GREEN_DRAGON_CONFIG, GreenDragonConfig, StoreConfig, FL_CATEGORIES

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
    config: GreenDragonConfig = None,
) -> List[Dict[str, Any]]:
    """
    Fetch a Sweed POS category menu page and extract product links.

    Green Dragon URL pattern:
        /{store_slug}/menu/{category}-{id}/{product-slug}

    Returns list of dicts with: product_slug, product_url, category, sweed_product_id
    """
    config = config or GREEN_DRAGON_CONFIG
    url = config.get_menu_url(store_slug, category_path)
    logger.info(f"  [{category}] Fetching menu: {url}")

    html = _get(client, url, config.rate_limit_sec)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    products: List[Dict[str, Any]] = []
    seen: set = set()

    # Product links: /{store}/menu/{category}-{id}/{slug}
    url_pattern = re.compile(
        rf"/{re.escape(store_slug)}/menu/{re.escape(category_path)}/([^\s?\"']+)"
    )

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        m = url_pattern.search(href)
        if not m:
            continue

        product_slug = m.group(1).split("?")[0].rstrip("/")
        if not product_slug or product_slug in seen:
            continue
        seen.add(product_slug)

        # Extract Sweed numeric product ID from end of slug (e.g., ...-440419)
        id_match = re.search(r"-(\d+)$", product_slug)
        sweed_id = id_match.group(1) if id_match else None

        product_url = config.get_product_url(store_slug, category_path, product_slug)

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
    config: GreenDragonConfig = None,
) -> Dict[str, Any]:
    """
    Fetch a Green Dragon product detail page and extract full lab data
    from the window.__sw JSON blob embedded in the page.

    Adds to the product dict:
        name, brand, strain_name, strain_type,
        thc_percent, cbd_percent,
        terpenes {name: value},
        flavors, effects,
        coa_url, batch_id,
        category_name, subcategory, price, weight,
        detail_source (window.__sw | html_fallback | none)
    """
    config = config or GREEN_DRAGON_CONFIG
    url = product.get("product_url", "")
    if not url:
        return product

    html = _get(client, url, config.rate_limit_sec)
    if not html:
        product["detail_error"] = "fetch_failed"
        return product

    # Primary: window.__sw JSON blob (dehydrated React Query cache)
    sw_data = _extract_from_sw_blob(html, product.get("sweed_product_id"))
    if sw_data:
        product.update(sw_data)
        product["detail_source"] = "window.__sw"
    else:
        # Fallback: plain HTML parsing (CSS classes OUIWQpt/zRYKXNN)
        html_data = _extract_from_html(html)
        if html_data:
            product.update(html_data)
            product["detail_source"] = "html_fallback"
        else:
            product["detail_source"] = "none"

    product["detail_scraped_at"] = datetime.now(timezone.utc).isoformat()
    return product


# ---- window.__sw extraction (Sweed POS — Green Dragon) ----

def _extract_from_sw_blob(html: str, variant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Extract product object from window.__sw (React Query cache injected by Sweed POS).

    Green Dragon data structure (verified Feb 2026):
      window.__sw = {
        "dehydratedState": {
          "queries": [
            {
              "state": {
                "data": {PRODUCT_OBJ}
              },
              "queryKey": ["/Products/GetProductByVariantId", ...]
            }
          ]
        }
      }

    Extraction strategy (proven in prototype v2):
      1. Regex-match ``window.__sw = {`` to find the blob start
      2. Find ``GetProductByVariantId`` query key
      3. Backtrack to nearest ``"state":{"data":{`` before that key
      4. Balanced-brace extraction to get the product JSON object
      5. json.loads() and normalize
    """
    # Find window.__sw = {...};
    m = re.search(r"window\.__sw\s*=\s*(\{.*?\});\s*</script>", html, re.DOTALL)
    if not m:
        return None

    raw = m.group(1)

    # Find GetProductByVariantId query key
    query_idx = raw.find("GetProductByVariantId")
    if query_idx < 0:
        return None

    # Backtrack to nearest '"state":{"data":{' before the query key
    data_marker = '"state":{"data":{'
    search_start = max(0, query_idx - 10000)
    data_idx = raw.rfind(data_marker, search_start, query_idx)
    if data_idx < 0:
        return None

    # Extract the product object using balanced-brace counting
    obj_start = data_idx + len('"state":{"data":')
    obj_str = raw[obj_start:]

    depth = 0
    end = 0
    for i, c in enumerate(obj_str):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and i > 0:
            end = i + 1
            break

    if end == 0:
        return None

    product_json = obj_str[:end]

    try:
        product_data = json.loads(product_json)
    except json.JSONDecodeError:
        product_data = _safe_parse_product(product_json)

    if not product_data:
        return None

    return _normalize_sw_product(product_data)


def _safe_parse_product(json_str: str) -> Optional[Dict]:
    """Try to parse a product JSON string, handling truncation edge cases."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        depth = 0
        for i, ch in enumerate(json_str):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth == 0 and i > 0:
                try:
                    return json.loads(json_str[: i + 1])
                except json.JSONDecodeError:
                    continue
    return None


def _normalize_sw_product(data: Dict) -> Dict[str, Any]:
    """Normalize Sweed POS product JSON (GetProductByVariantId) into Terprint standard format.

    Verified structure (Green Dragon, Feb 2026):
      data.name, data.id
      data.brand.name
      data.strain.name, .prevalence.name, .terpenes[{name, value}]
      data.category.name, data.subcategory.name
      data.effects[{name}]
      data.variants[0].labTests.thc.value[0]   — THC%
      data.variants[0].labTests.cbd.value[0]   — CBD%
      data.variants[0].labTests.fullLabDataUrl  — LabDrive COA URL
      data.variants[0].id                       — variant/batch ID
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
        result["brand"]       = brand.get("name", "").strip()
        result["brand_id"]    = brand.get("id")
        result["brand_image"] = brand.get("imageUrl")

    # Strain / genetics
    strain = data.get("strain")
    if isinstance(strain, dict):
        result["strain_name"] = strain.get("name", "").strip()
        prevalence = strain.get("prevalence")
        if isinstance(prevalence, dict):
            result["strain_type"] = prevalence.get("name", "")  # Indica/Sativa/Hybrid

        # Terpenes from strain object (Green Dragon has populated terpene data)
        terps = strain.get("terpenes") or []
        if terps:
            result["terpenes"] = {
                t.get("name", f"terp_{i}"): float(t.get("value", 0))
                for i, t in enumerate(terps) if isinstance(t, dict)
            }

        # Flavors from strain object
        flavors = strain.get("flavors") or []
        if flavors:
            result["flavors"] = [
                f.get("name", str(f)) if isinstance(f, dict) else str(f)
                for f in flavors
            ]

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

    # Variant / batch ID
    v_id = variant.get("id")
    if v_id:
        result["variant_id"] = str(v_id)

    # Lab tests
    lab = variant.get("labTests") or {}

    # THC: labTests.thc.value = [22.8]
    thc_obj = lab.get("thc")
    if isinstance(thc_obj, dict):
        thc_vals = thc_obj.get("value") or []
        if thc_vals:
            try:
                result["thc_percent"] = float(thc_vals[0])
            except (TypeError, ValueError):
                pass

    # CBD: labTests.cbd.value = [0.04]
    cbd_obj = lab.get("cbd")
    if isinstance(cbd_obj, dict):
        cbd_vals = cbd_obj.get("value") or []
        if cbd_vals:
            try:
                result["cbd_percent"] = float(cbd_vals[0])
            except (TypeError, ValueError):
                pass

    # COA URL: labTests.fullLabDataUrl (LabDrive / Method Testing Labs)
    coa_url = lab.get("fullLabDataUrl")
    if coa_url and isinstance(coa_url, str) and coa_url.startswith("http"):
        result["coa_url"] = coa_url

    # Fallback: check other keys
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

    # Available quantity
    avail = variant.get("availableQty")
    if avail is not None:
        result["available_qty"] = avail

    # Detailed lab data
    result["has_detailed_lab"] = variant.get("detailedLabDataExists", False)
    detailed = variant.get("detailedLabTestShort")
    if detailed and isinstance(detailed, dict):
        result["detailed_lab"] = detailed

    # Batch info (documents/images)
    batch = variant.get("batch")
    if batch and isinstance(batch, dict):
        docs = batch.get("documents", [])
        if docs:
            result["batch_documents"] = docs
        imgs = batch.get("images", [])
        if imgs:
            result["batch_images"] = imgs

    return result


# ---- HTML fallback (when window.__sw is absent) ----

def _extract_from_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Fallback: parse the rendered HTML of a Green Dragon product page.

    Sweed POS React uses CSS modules — lab data is rendered as
    label/value pairs using two sibling divs:
      <div class="OUIWQpt">Total THC</div>
      <div class="zRYKXNN">22.8%</div>
    """
    result: Dict[str, Any] = {}
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = soup.find("h1") or soup.find("h2")
    if title:
        result["name"] = title.get_text(strip=True)

    # ---- Lab data via CSS classes ----
    def _find_value_el(label_el):
        """Return the zRYKXNN value element adjacent to a label element."""
        sibling = label_el.find_next_sibling()
        if sibling and "zRYKXNN" in sibling.get("class", []):
            return sibling
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
            result["strain_type"] = val_text.lstrip("#").strip()
        elif label_text == "strain":
            result["strain_name"] = val_text.lstrip("#").strip()
        elif "subcategory" in label_text:
            result["subcategory"] = val_text.lstrip("#").strip()
        elif "total size" in label_text:
            result["weight"] = val_text

    # ---- Regex fallback for THC/CBD ----
    if "thc_percent" not in result:
        thc_m = re.search(r"Total\s*THC\s*([0-9]+\.?[0-9]*)\s*%", html, re.IGNORECASE)
        if thc_m:
            result["thc_percent"] = float(thc_m.group(1))

    if "cbd_percent" not in result:
        cbd_m = re.search(r"Total\s*CBD\s*([0-9]+\.?[0-9]*)\s*%", html, re.IGNORECASE)
        if cbd_m:
            result["cbd_percent"] = float(cbd_m.group(1))

    # Brand from "by #BrandName" pattern
    brand_match = re.search(r"by <!-- -->#<!-- -->([^<]+)", html)
    if brand_match:
        result["brand"] = brand_match.group(1).strip()

    # og:image
    og = re.search(r'property="og:image"\s+content="([^"]+)"', html)
    if og:
        result["image_url"] = og.group(1)

    # ---- COA URL — LabDrive links ----
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        href = a["href"]
        if (
            "coa" in text
            or "lab report" in text
            or "certificate" in text
            or href.endswith(".pdf")
            or "labdrive.net" in href
        ):
            if href.startswith("http"):
                result["coa_url"] = href
                break

    return result if result.get("name") or result.get("thc_percent") else None


# ---------------------------------------------------------------------------
# Layer 3: COA PDF download (LabDrive)
# ---------------------------------------------------------------------------

def download_coa(
    client: httpx.Client,
    coa_url: str,
    output_dir: str,
    filename_base: str,
    rate_limit: float = 1.5,
) -> Optional[str]:
    """
    Download a COA PDF from LabDrive or other URL.

    Green Dragon COAs are on mete.labdrive.net (Method Testing Labs).
    Flow: share URL → HTML landing page → find download <a> → follow to PDF.
    """
    if not coa_url or coa_url.startswith("javascript:") or coa_url == "#":
        return None

    os.makedirs(output_dir, exist_ok=True)

    try:
        time.sleep(rate_limit)
        resp = client.get(coa_url, follow_redirects=True, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"    COA HTTP {resp.status_code}: {coa_url}")
            return None

        content_type = resp.headers.get("content-type", "").lower()

        # Direct PDF
        if "pdf" in content_type:
            filepath = os.path.join(output_dir, f"{filename_base}.pdf")
            with open(filepath, "wb") as f:
                f.write(resp.content)
            logger.info(f"    COA saved: {filename_base}.pdf ({len(resp.content):,} bytes)")
            return filepath

        # HTML page — LabDrive landing page with download link
        if "html" in content_type:
            soup = BeautifulSoup(resp.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True).lower()
                if "download" in text or ".pdf" in href.lower():
                    abs_url = href
                    if href.startswith("/"):
                        parsed = resp.url
                        abs_url = f"{parsed.scheme}://{parsed.host}{href}"
                    return download_coa(client, abs_url, output_dir, filename_base, rate_limit)

            for tag in soup.find_all(["embed", "iframe", "object"]):
                src = tag.get("src") or tag.get("data")
                if src and ".pdf" in src.lower():
                    if src.startswith("/"):
                        parsed = resp.url
                        src = f"{parsed.scheme}://{parsed.host}{src}"
                    return download_coa(client, src, output_dir, filename_base, rate_limit)

            # Save HTML for inspection
            filepath = os.path.join(output_dir, f"{filename_base}_coa_page.html")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(resp.text)
            logger.info(f"    COA is HTML page, saved: {filename_base}_coa_page.html")
            return filepath

        # Unknown content — save as-is
        ext = "pdf" if "pdf" in coa_url.lower() else "bin"
        filepath = os.path.join(output_dir, f"{filename_base}.{ext}")
        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath

    except Exception as e:
        logger.warning(f"    COA download failed: {coa_url} — {e}")
        return None


# ---------------------------------------------------------------------------
# High-level: scrape a full store
# ---------------------------------------------------------------------------

class GreenDragonStoreScraper:
    """
    Scrapes all products for a single Green Dragon Florida store.

    Usage:
        scraper = GreenDragonStoreScraper()
        result  = scraper.scrape_store(store)
    """

    def __init__(self, config: GreenDragonConfig = None):
        self.config = config or GREEN_DRAGON_CONFIG

    def scrape_store(
        self,
        store: StoreConfig,
        categories: Optional[Dict[str, str]] = None,
        include_details: bool = True,
        include_coa: bool = False,
        coa_output_dir: Optional[str] = None,
        max_products: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Scrape all categories for one store.

        Returns:
            {
                "dispensary":     "green_dragon",
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
        coa_count = 0

        with httpx.Client(follow_redirects=True, timeout=self.config.request_timeout_sec) as client:
            for category_name, category_path in categories.items():
                logger.info(f"Store [{store.slug}] - category: {category_name}")
                products = scrape_menu_links(
                    client, store.slug, category_name, category_path, self.config
                )

                if include_details:
                    limit = min(len(products), max_products) if max_products else len(products)
                    for i in range(limit):
                        p = products[i]
                        logger.info(
                            f"  [{category_name}] Detail {i+1}/{limit}: "
                            f"{p.get('product_slug', '?')[:50]}"
                        )
                        scrape_product_detail(client, p, self.config)

                # COA downloads
                if include_coa and coa_output_dir:
                    coa_dir = os.path.join(coa_output_dir, store.slug)
                    for p in products:
                        coa_url = p.get("coa_url")
                        if coa_url:
                            slug = p.get("product_slug", "unknown")[:80]
                            safe_name = re.sub(r"[^\w\-]", "_", slug)
                            filepath = download_coa(
                                client, coa_url, coa_dir, safe_name, self.config.rate_limit_sec
                            )
                            if filepath:
                                p["coa_file"] = filepath
                                p["coa_downloaded"] = True
                                coa_count += 1
                            else:
                                p["coa_downloaded"] = False

                all_products.extend(products)

                if max_products and len(all_products) >= max_products:
                    logger.info(f"  Reached max_products={max_products}, stopping.")
                    break

        return {
            "dispensary":    "green_dragon",
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
                "include_coa":        include_coa,
                "coa_downloaded":     coa_count,
                "coa_source":         f"LabDrive ({self.config.coa_host})",
                "scraper_version":    "2.0",
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

    parser = argparse.ArgumentParser(description="Green Dragon scraper smoke test")
    parser.add_argument("--store",    default="avon",   help="Store slug (default: avon)")
    parser.add_argument("--category", default="flower", help="Category (default: flower)")
    parser.add_argument("--limit",    type=int, default=3, help="Max products (default: 3)")
    parser.add_argument("--no-details", action="store_true", help="Skip product detail pages")
    parser.add_argument("--coa",      action="store_true", help="Download COA PDFs")
    args = parser.parse_args()

    try:
        from config import GREEN_DRAGON_CONFIG, FL_STORES, FL_CATEGORIES
        from config import get_store_by_slug
    except ImportError:
        from terprint_menu_downloader.dispensaries.green_dragon.config import (
            GREEN_DRAGON_CONFIG, FL_STORES, FL_CATEGORIES, get_store_by_slug
        )

    store = get_store_by_slug(args.store)
    if not store:
        print(f"Unknown store slug: {args.store}")
        print(f"Available: {[s.slug for s in FL_STORES]}")
        sys.exit(1)

    categories = {args.category: FL_CATEGORIES[args.category]} if args.category in FL_CATEGORIES else FL_CATEGORIES

    scraper = GreenDragonStoreScraper()
    result  = scraper.scrape_store(
        store,
        categories=categories,
        include_details=not args.no_details,
        include_coa=args.coa,
        coa_output_dir="output/green_dragon/coa" if args.coa else None,
        max_products=args.limit,
    )

    print(f"\n=== {result['store_name']} ===")
    print(f"Products: {result['product_count']}")
    for p in result["products"][:args.limit]:
        thc   = p.get("thc_percent")
        terps = list(p.get("terpenes", {}).keys())[:3]
        coa   = "COA" if p.get("coa_url") else "no COA"
        print(f"  {p.get('name','?')}  THC={thc}%  terpenes={terps}  {coa}")
