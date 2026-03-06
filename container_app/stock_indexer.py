"""
Stock Index Builder v2

Builds comprehensive, multi-dispensary stock index from menu downloads.
Enriches with SQL batch data (COA), genetics data, and store locations.

Architecture (v2):
    Menu Files (all dispensaries) → Base stock items
    + SQL Batch Data → THC/CBD/terpene enrichment
    + Genetics Data → Strain type, lineage
    + Location Data → Store coordinates, addresses

Outputs:
    stock-index/current.json         Full flat index
    stock-index/by-dispensary/*.json  Per-dispensary files
    stock-index/by-store/*.json      Per-store files
    stock-index/summary.json         Lightweight dashboard data
    stock-index/metadata.json        Build metadata

Copyright (c) 2026 Acidni LLC
"""

import json
import hashlib
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class StoreInfo:
    """Store location data."""
    store_id: str = ""
    store_name: str = ""
    city: str = ""
    state: str = "FL"
    latitude: float | None = None
    longitude: float | None = None
    address: str = ""


@dataclass
class Cannabinoids:
    """Cannabinoid percentages from COA data."""
    thc_percent: float | None = None
    cbd_percent: float | None = None
    cbg_percent: float | None = None
    thca_percent: float | None = None
    cbda_percent: float | None = None


@dataclass
class TerpeneProfile:
    """Terpene analysis data."""
    total_percent: float | None = None
    top_3: list[str] = field(default_factory=list)
    profile: dict[str, float] = field(default_factory=dict)


@dataclass
class GeneticsInfo:
    """Strain genetics cross-reference."""
    strain_type: str | None = None
    parent_1: str | None = None
    parent_2: str | None = None
    has_full_genetics: bool = False


@dataclass
class PricingInfo:
    """Product pricing data."""
    price: float | None = None
    weight_grams: float | None = None
    price_per_gram: float | None = None
    on_sale: bool = False


@dataclass
class AvailabilityInfo:
    """Stock availability and freshness."""
    in_stock: bool = True
    first_seen: str = ""
    last_seen: str = ""
    went_out_of_stock_at: str | None = None
    freshness_hours: float | None = None
    days_in_stock: float | None = None
    times_restocked: int = 0
    confidence: str = "medium"


@dataclass
class StockItemV2:
    """A product in stock — v2 schema with full enrichment."""
    id: str = ""
    strain: str = ""
    strain_slug: str = ""
    product_name: str = ""
    dispensary: str = ""
    dispensary_name: str = ""
    category: str = ""
    batch_id: str = ""

    store: StoreInfo = field(default_factory=StoreInfo)
    cannabinoids: Cannabinoids = field(default_factory=Cannabinoids)
    terpenes: TerpeneProfile = field(default_factory=TerpeneProfile)
    genetics: GeneticsInfo = field(default_factory=GeneticsInfo)
    pricing: PricingInfo = field(default_factory=PricingInfo)
    availability: AvailabilityInfo = field(default_factory=AvailabilityInfo)

    links: dict[str, str] = field(default_factory=dict)
    source: str = "menu"
    source_file: str = ""


# Dispensary display name mapping
DISPENSARY_NAMES: dict[str, str] = {
    "trulieve": "Trulieve",
    "cookies": "Cookies",
    "muv": "MÜV",
    "flowery": "Flowery",
    "curaleaf": "Curaleaf",
    "sunnyside": "Sunnyside",
    "sunburn": "Sunburn",
    "green_dragon": "Green Dragon",
    "sanctuary": "Sanctuary Medicinals",
}

# All dispensaries we track
EXPECTED_DISPENSARIES = list(DISPENSARY_NAMES.keys())

# Keys to exclude from terpene profiles (these are aggregates, not individual terpenes)
_TERPENE_SKIP_KEYS = {"total", "total_terpenes", "sum", "total_percent"}


class StockIndexerV2:
    """
    Builds v2 stock index from blob menu files, enriched with SQL + genetics.

    Strategy:
        1. Scan ALL dispensary menu files from blob storage (today, then yesterday)
        2. Merge enrichment from SQL batch data (optional — if DB reachable)
        3. Cross-reference genetics index for strain type/lineage
        4. Apply store location data from dispensary_locations.json
        5. Output: current.json + partitioned files + summary.json
    """

    SQL_SERVER = "acidni-sql.database.windows.net"
    SQL_DATABASE = "terprint"
    SQL_USER = "adm"
    SQL_PASSWORD = "sql1234%"

    def __init__(self):
        self.sql_password = os.environ.get("SQL_PASSWORD", self.SQL_PASSWORD)
        self.INDEX_PREFIX = "stock-index"
        self.locations = self._load_locations()
        self._container = None
        self._genetics_cache: dict[str, dict] | None = None

    # =========================================================================
    # Blob Storage
    # =========================================================================

    def _get_blob_container(self):
        """Get jsonfiles blob container."""
        if self._container is not None:
            return self._container
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            svc = BlobServiceClient(
                account_url="https://stterprintsharedgen2.blob.core.windows.net",
                credential=credential,
            )
            self._container = svc.get_container_client("jsonfiles")
            return self._container
        except Exception as e:
            logger.error(f"Failed to init blob container: {e}")
            return None

    def _get_genetics_container(self):
        """Get genetics-data blob container."""
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            svc = BlobServiceClient(
                account_url="https://stterprintsharedgen2.blob.core.windows.net",
                credential=credential,
            )
            return svc.get_container_client("genetics-data")
        except Exception as e:
            logger.warning(f"Failed to init genetics container: {e}")
            return None

    # =========================================================================
    # Location Data
    # =========================================================================

    def _load_locations(self) -> dict:
        """Load dispensary_locations.json."""
        path = os.path.join(os.path.dirname(__file__), "dispensary_locations.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load location data: {e}")
            return {}

    def _resolve_store(self, dispensary: str, raw_store: str) -> StoreInfo:
        """Resolve a raw store identifier to full StoreInfo with coordinates.

        Handles blob filenames like:
            curaleaf_products_store_curaleaf-tampa-dale-mabry-midtown_20260301_230805
            cookies_menu_cookies-miami_20260301_120000
        Extracts city slug and matches against dispensary_locations.json keys.
        """
        disp_locations = self.locations.get(dispensary, {})
        normalized = raw_store.lower().replace(" ", "-").replace("_", "-") if raw_store else ""

        # Strip dispensary prefix and timestamp suffix from blob filenames
        # Pattern: {dispensary}[-_]...{city-slug}[-_]{YYYYMMDD}[-_]{HHMMSS}
        clean = normalized
        # Remove common prefixes like "curaleaf-products-store-curaleaf-"
        # Normalize dispensary name to match (underscores → hyphens) since
        # normalized already replaced all underscores with hyphens.
        disp_norm = dispensary.replace("_", "-")
        for prefix in (
            f"{disp_norm}-products-store-{disp_norm}-",
            f"{disp_norm}-products-store-",
            f"{disp_norm}-menu-{disp_norm}-",
            f"{disp_norm}-menu-",
            f"{disp_norm}-store-",
            f"{disp_norm}-",
        ):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break
        # Remove timestamp suffix (YYYYMMDD-HHMMSS or YYYYMMDD)
        clean = re.sub(r"-?\d{8}(-\d{6})?$", "", clean).strip("-")
        # Remove Trulieve category suffix (e.g., -cat-mja5 from store_miami_cat-MjA5)
        clean = re.sub(r"-cat-[a-z0-9]+$", "", clean).strip("-")

        # Try matching: exact → cleaned → partial contains
        loc = disp_locations.get(normalized) or disp_locations.get(clean)

        if not loc:
            # Partial match: check if any location key appears in the cleaned store name
            for loc_key, loc_data in disp_locations.items():
                if loc_key in clean or clean in loc_key:
                    loc = loc_data
                    clean = loc_key
                    break

        if not loc:
            loc = {}

        city = clean.replace("-", " ").replace("_", " ").title() if clean else ""

        return StoreInfo(
            store_id=f"{dispensary}-{clean}" if clean else dispensary,
            store_name=f"{DISPENSARY_NAMES.get(dispensary, dispensary)} {city}".strip(),
            city=city,
            state="FL",
            latitude=loc.get("lat"),
            longitude=loc.get("lng"),
            address=loc.get("address", ""),
        )

    # =========================================================================
    # Genetics Data
    # =========================================================================

    def _load_genetics_index(self) -> dict[str, dict]:
        """Load genetics index from blob storage. Cached after first call."""
        if self._genetics_cache is not None:
            return self._genetics_cache

        self._genetics_cache = {}
        try:
            container = self._get_genetics_container()
            if not container:
                return self._genetics_cache

            blob = container.get_blob_client("index/strains-index.json")
            content = blob.download_blob().readall()
            data = json.loads(content)
            self._genetics_cache = data.get("strains", {})
            logger.info(f"Loaded genetics index: {len(self._genetics_cache)} strains")
        except Exception as e:
            logger.warning(f"Could not load genetics index: {e}")

        return self._genetics_cache

    def _get_genetics_for_strain(self, strain_slug: str) -> GeneticsInfo:
        """Look up genetics data for a strain slug."""
        index = self._load_genetics_index()
        info = index.get(strain_slug)
        if not info:
            return GeneticsInfo()

        return GeneticsInfo(
            strain_type=info.get("type"),
            parent_1=None,  # Index only has basic info; full data in partitions
            parent_2=None,
            has_full_genetics=info.get("has_lineage", False),
        )

    def _load_genetics_partition(self, partition_key: str) -> dict[str, dict]:
        """Load a single genetics partition for full strain data."""
        try:
            container = self._get_genetics_container()
            if not container:
                return {}
            blob = container.get_blob_client(f"partitions/{partition_key}.json")
            content = blob.download_blob().readall()
            data = json.loads(content)
            result = {}
            for strain in data.get("strains", []):
                slug = strain.get("strain_slug", "")
                if slug:
                    result[slug] = strain
            return result
        except Exception:
            return {}

    def _enrich_genetics(self, item: StockItemV2) -> None:
        """Enrich a stock item with genetics data."""
        slug = item.strain_slug
        if not slug:
            return

        index = self._load_genetics_index()
        info = index.get(slug)
        if not info:
            return

        item.genetics.strain_type = info.get("type")
        item.genetics.has_full_genetics = info.get("has_lineage", False)

        # Load partition for parent data if available
        if info.get("has_lineage"):
            partition_key = info.get("partition", "other")
            partition_data = self._load_genetics_partition(partition_key)
            full = partition_data.get(slug)
            if full:
                item.genetics.parent_1 = full.get("parent_1")
                item.genetics.parent_2 = full.get("parent_2")

    # =========================================================================
    # SQL Enrichment
    # =========================================================================

    def _get_db_connection(self):
        """Get SQL database connection."""
        import pymssql

        return pymssql.connect(
            server=self.SQL_SERVER,
            user=self.SQL_USER,
            password=self.sql_password,
            database=self.SQL_DATABASE,
            port=1433,
            timeout=30,
        )

    def _load_sql_enrichment(self, max_age_days: int = 7) -> dict[str, dict]:
        """
        Load enrichment data from SQL Batch table.
        Returns dict keyed by (dispensary, strain_normalized) → enrichment data.
        """
        enrichment: dict[str, dict] = {}
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(as_dict=True)

            query = """
            SELECT
                BatchId, ProductName, Strain, Dispensary, Category,
                ThcPercent, CbdPercent, CbgPercent, ThcaPercent, CbdaPercent,
                Terpenes, TerpenesTotal,
                Price, WeightGrams,
                StoreLocation, StoreName, Latitude, Longitude, Address,
                LastSeen, ProcessedDate
            FROM Batch
            WHERE InStock = 1
                AND LastSeen >= DATEADD(day, %s, GETDATE())
            ORDER BY LastSeen DESC
            """

            cursor.execute(query, (-max_age_days,))
            rows = cursor.fetchall()
            logger.info(f"SQL enrichment: {len(rows)} in-stock rows from database")

            for row in rows:
                strain = row.get("Strain", "")
                dispensary = (row.get("Dispensary") or "").lower()
                normalized = self.normalize_strain_name(strain)
                key = f"{dispensary}:{normalized}"

                # Keep first (most recent) row per key
                if key not in enrichment:
                    enrichment[key] = row

            cursor.close()
            conn.close()
            logger.info(f"SQL enrichment loaded: {len(enrichment)} unique items")
        except Exception as e:
            logger.warning(f"SQL enrichment failed (will use menu data only): {e}")

        return enrichment

    def _apply_sql_enrichment(self, item: StockItemV2, sql_row: dict) -> None:
        """Apply SQL batch data to a stock item."""
        item.source = "database+menu"
        item.batch_id = sql_row.get("BatchId") or item.batch_id

        # Cannabinoids
        item.cannabinoids.thc_percent = _safe_float(sql_row.get("ThcPercent")) or item.cannabinoids.thc_percent
        item.cannabinoids.cbd_percent = _safe_float(sql_row.get("CbdPercent")) or item.cannabinoids.cbd_percent
        item.cannabinoids.cbg_percent = _safe_float(sql_row.get("CbgPercent"))
        item.cannabinoids.thca_percent = _safe_float(sql_row.get("ThcaPercent"))
        item.cannabinoids.cbda_percent = _safe_float(sql_row.get("CbdaPercent"))

        # Terpenes
        terpenes_raw = sql_row.get("Terpenes")
        if terpenes_raw:
            try:
                profile = json.loads(terpenes_raw) if isinstance(terpenes_raw, str) else terpenes_raw
                if isinstance(profile, dict):
                    item.terpenes.profile = profile
                    sorted_terps = sorted(profile.items(), key=lambda x: x[1], reverse=True)
                    item.terpenes.top_3 = [t[0] for t in sorted_terps[:3]]
                    item.terpenes.total_percent = _safe_float(sql_row.get("TerpenesTotal"))
            except (json.JSONDecodeError, TypeError):
                pass

        # Pricing (prefer SQL if available)
        sql_price = _safe_float(sql_row.get("Price"))
        sql_weight = _safe_float(sql_row.get("WeightGrams"))
        if sql_price:
            item.pricing.price = sql_price
        if sql_weight:
            item.pricing.weight_grams = sql_weight
        if item.pricing.price and item.pricing.weight_grams and item.pricing.weight_grams > 0:
            item.pricing.price_per_gram = round(item.pricing.price / item.pricing.weight_grams, 2)

        # Store location from SQL (may have better data)
        sql_store = sql_row.get("StoreLocation")
        if sql_store:
            resolved = self._resolve_store(item.dispensary, sql_store)
            # Only override if SQL has coordinates and current doesn't
            if resolved.latitude and not item.store.latitude:
                item.store = resolved

        # Availability
        last_seen = sql_row.get("LastSeen")
        if last_seen:
            try:
                if hasattr(last_seen, "isoformat"):
                    item.availability.last_seen = last_seen.isoformat()
                else:
                    item.availability.last_seen = str(last_seen)
                item.availability.confidence = "high"
            except Exception:
                pass

    # =========================================================================
    # Menu File Processing
    # =========================================================================

    def _find_latest_menu_blobs(self, dispensary: str, max_days_back: int = 3) -> list:
        """
        Find the most recent menu blobs for a dispensary.

        Smart filtering:
        - Prefers summary files when available (contain all products consolidated)
        - For per-store/category files (e.g. Trulieve), deduplicates to one file per store
        - Excludes batch_list files and other non-menu artifacts
        - Caps at MAX_BLOBS_PER_DISPENSARY to prevent resource exhaustion
        """
        MAX_BLOBS_PER_DISPENSARY = 50

        container = self._get_blob_container()
        if not container:
            return []

        for days_back in range(max_days_back):
            check_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            date_str = check_date.strftime("%Y/%m/%d")
            prefix = f"dispensaries/{dispensary}/{date_str}/"

            raw_blobs = list(container.list_blobs(name_starts_with=prefix))
            if not raw_blobs:
                continue

            # --- Filter out non-menu files ---
            menu_blobs = []
            summary_blob = None
            for b in raw_blobs:
                fname = b.name.split("/")[-1].lower()
                # Skip batch lists, genetics exports, etc.
                if "batch_list" in fname or "genetics" in fname:
                    continue
                # Detect summary files (e.g. trulieve_products_summary_*.json)
                if "summary" in fname:
                    summary_blob = b
                    continue
                menu_blobs.append(b)

            # --- If a summary file exists, validate it has actual products ---
            # Some dispensaries (e.g. Trulieve) create "summary" files that are
            # manifests (containing file lists, batch counts) rather than product
            # arrays.  Only prefer the summary if it contains real products.
            if summary_blob:
                try:
                    _sc = container.get_blob_client(summary_blob.name)
                    _sd = json.loads(_sc.download_blob().readall())
                    _sp = self._extract_products(_sd)
                    if len(_sp) > 0:
                        logger.info(
                            f"Using summary file for {dispensary} ({days_back}d ago): "
                            f"{summary_blob.name} ({len(_sp)} products, "
                            f"skipping {len(menu_blobs)} individual files)"
                        )
                        return [summary_blob]
                    else:
                        logger.info(
                            f"Summary file for {dispensary} is a manifest (0 products), "
                            f"falling through to {len(menu_blobs)} per-store files"
                        )
                except Exception as _e:
                    logger.warning(f"Could not validate summary file for {dispensary}: {_e}")

            # --- Deduplicate per-store files ---
            # Trulieve creates per-store-per-category files:
            #   trulieve_products_store-venice_cat-MjA8_20260302_010337.json
            # We want one file per store (the latest/largest).
            if len(menu_blobs) > MAX_BLOBS_PER_DISPENSARY:
                store_best: dict[str, Any] = {}
                for b in menu_blobs:
                    fname = b.name.split("/")[-1]
                    # Extract store identifier from filename
                    store_key = self._extract_store_from_filename(fname, dispensary)
                    existing = store_best.get(store_key)
                    if not existing or (b.size and existing.size and b.size > existing.size):
                        store_best[store_key] = b

                menu_blobs = list(store_best.values())
                logger.info(
                    f"Deduplicated {dispensary} to {len(menu_blobs)} store-level blobs "
                    f"(from {len(raw_blobs)} total files)"
                )

            # --- Cap ---
            menu_blobs.sort(key=lambda b: b.name, reverse=True)
            if len(menu_blobs) > MAX_BLOBS_PER_DISPENSARY:
                logger.warning(
                    f"Capping {dispensary} blobs from {len(menu_blobs)} to {MAX_BLOBS_PER_DISPENSARY}"
                )
                menu_blobs = menu_blobs[:MAX_BLOBS_PER_DISPENSARY]

            logger.info(f"Found {len(menu_blobs)} menu blobs for {dispensary} ({days_back}d ago)")
            return menu_blobs

        logger.warning(f"No menu files for {dispensary} in last {max_days_back} days")
        return []

    @staticmethod
    def _extract_store_from_filename(filename: str, dispensary: str) -> str:
        """
        Extract a store identifier from a blob filename for deduplication.

        Examples:
            trulieve_products_store-venice_cat-MjA8_20260302_010337.json → venice
            cookies_bradenton_menu_20260302_010420.json → bradenton
            curaleaf_products_store_curaleaf-tampa_20260301_230805.json → tampa
        """
        name = filename.replace(".json", "").lower()

        # Remove timestamp suffix (YYYYMMDD_HHMMSS)
        import re as _re
        name = _re.sub(r"_\d{8}_\d{6}$", "", name)

        # Trulieve pattern: store-{store}_cat-{cat}
        m = _re.search(r"store[_-]([^_]+?)(?:_cat[_-]|$)", name)
        if m:
            return m.group(1)

        # Generic: strip dispensary prefix, return remainder
        for prefix in [f"{dispensary}_products_store_{dispensary}-",
                       f"{dispensary}_products_store_",
                       f"{dispensary}_products_",
                       f"{dispensary}_"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        # Remove trailing _menu or similar suffixes
        name = _re.sub(r"_menu$", "", name)
        return name or filename

    def _process_menu_blob(self, blob_name: str, dispensary: str) -> list[StockItemV2]:
        """Process a single menu JSON file into StockItemV2 objects."""
        try:
            container = self._get_blob_container()
            if not container:
                return []

            blob_client = container.get_blob_client(blob_name)
            content = blob_client.download_blob().readall()
            data = json.loads(content)

            products = self._extract_products(data)
            items = []
            now_iso = datetime.now(timezone.utc).isoformat()

            # Determine store from blob path if possible
            # Pattern: dispensaries/{dispensary}/{YYYY}/{MM}/{DD}/{store_or_file}.json
            path_parts = blob_name.split("/")
            raw_store = ""
            if len(path_parts) >= 6:
                filename = path_parts[-1].replace(".json", "")
                # If filename looks like a store name (not a timestamp)
                if not filename.replace("-", "").replace("_", "").isdigit():
                    raw_store = filename

            store = self._resolve_store(dispensary, raw_store)

            for product in products:
                if not isinstance(product, dict):
                    continue

                # ---------------------------------------------------------
                # Dispensary-specific extraction overrides
                # ---------------------------------------------------------
                strain = None
                batch_id = None
                category = None
                product_name = None
                thc = None
                cbd = None
                price = None
                weight = None
                strain_type = None
                terpene_profile: dict[str, float] = {}

                if dispensary == "trulieve":
                    # Trulieve: strain/category/THC live in custom_attributes_product[]
                    custom_attrs = product.get("custom_attributes_product")
                    if isinstance(custom_attrs, list):
                        attr_map = {}
                        for attr in custom_attrs:
                            if isinstance(attr, dict):
                                code = attr.get("code", "")
                                val = attr.get("value", "")
                                if code and val:
                                    attr_map[code] = val
                        strain = attr_map.get("strain") or attr_map.get("product_display_name")
                        strain_type = (attr_map.get("strain_type") or "").lower() or None
                        thc = _safe_float(attr_map.get("thc_percentage") or attr_map.get("thc_content"))
                        cbd = _safe_float(attr_map.get("cbd_percentage") or attr_map.get("cbd_content"))

                    # Trulieve category: from categories[].name array
                    # Categories are hierarchical: ["Brands", "Sunshine Cannabis", "Flower", "3.5g", "Minis"]
                    # The first few are brand hierarchies under url_path "brands/...", we want the product type
                    _TRULIEVE_SKIP_CATEGORIES = {
                        "brands", "bundle deals", "accessories", "bundles",
                        "new arrivals", "sale", "clearance", "best sellers",
                    }
                    _TRULIEVE_PRODUCT_CATEGORIES = {
                        "flower", "concentrates", "edibles", "vapes", "vaporizers", "cartridges",
                        "pre-rolls", "pre-roll", "topicals", "tinctures", "capsules", "rso",
                        "minis", "ground", "whole flower", "diamonds", "live rosin", "live resin",
                        "shatter", "wax", "crumble", "budder", "distillate", "syringes", "dabs",
                    }
                    cats = product.get("categories")
                    if isinstance(cats, list):
                        for cat_item in cats:
                            if isinstance(cat_item, dict):
                                cat_name = cat_item.get("name", "")
                                cat_url = cat_item.get("url_path", "")
                            elif isinstance(cat_item, str):
                                cat_name = cat_item
                                cat_url = ""
                            else:
                                continue
                            cat_lower = cat_name.lower() if cat_name else ""
                            # Skip if it's a brand, non-product category, or under brands/ path
                            if cat_lower in _TRULIEVE_SKIP_CATEGORIES:
                                continue
                            if cat_url.startswith("brands/"):
                                continue  # Brand sub-category like "brands/sunshine-cannabis"
                            # Prefer actual product type categories
                            if cat_lower in _TRULIEVE_PRODUCT_CATEGORIES:
                                category = cat_name
                                break
                        # Fallback: if no product category found, take first non-skipped
                        if not category and isinstance(cats, list):
                            for cat_item in cats:
                                if isinstance(cat_item, dict):
                                    cat_name = cat_item.get("name", "")
                                    cat_url = cat_item.get("url_path", "")
                                elif isinstance(cat_item, str):
                                    cat_name = cat_item
                                    cat_url = ""
                                else:
                                    continue
                                cat_lower = cat_name.lower() if cat_name else ""
                                if cat_lower not in _TRULIEVE_SKIP_CATEGORIES and not cat_url.startswith("brands/"):
                                    category = cat_name
                                    break

                    # Trulieve pricing: price_range.minimum_price.final_price.value
                    price_range = product.get("price_range", {})
                    min_price = price_range.get("minimum_price", {}) if isinstance(price_range, dict) else {}
                    if isinstance(min_price, dict):
                        fp = min_price.get("final_price", {})
                        if isinstance(fp, dict):
                            price = _safe_float(fp.get("value"))
                        if price is None:
                            rp = min_price.get("regular_price", {})
                            if isinstance(rp, dict):
                                price = _safe_float(rp.get("value"))

                    product_name = product.get("name") or strain
                    batch_id = str(product.get("sku") or product.get("id") or "unknown")

                elif dispensary == "muv":
                    # MUV: strain is nested {name, prevalence: {name}}
                    strain_obj = product.get("strain")
                    if isinstance(strain_obj, dict):
                        strain = strain_obj.get("name")
                        prevalence = strain_obj.get("prevalence")
                        if isinstance(prevalence, dict):
                            strain_type = (prevalence.get("name") or "").lower() or None
                    cat_obj = product.get("category")
                    if isinstance(cat_obj, dict):
                        category = cat_obj.get("name")
                    elif isinstance(cat_obj, str):
                        category = cat_obj
                    product_name = product.get("name")

                    # MUV: pricing/weight from variants list
                    variants = product.get("variants")
                    if isinstance(variants, list) and variants:
                        v0 = variants[0] if isinstance(variants[0], dict) else {}
                        price = _safe_float(v0.get("promoPrice") or v0.get("price"))
                        unit_size = v0.get("unitSize")
                        if isinstance(unit_size, dict):
                            weight = _safe_float(unit_size.get("value"))

                elif dispensary == "flowery":
                    # Flowery: strain is nested, categories is array, rich terpenes
                    strain_obj = product.get("strain")
                    if isinstance(strain_obj, dict):
                        strain = strain_obj.get("name")
                        strain_type = (strain_obj.get("lineage") or "").lower() or None
                    categories_arr = product.get("categories")
                    if isinstance(categories_arr, list) and categories_arr:
                        category = str(categories_arr[0])
                    product_name = product.get("name")
                    price = _safe_float(product.get("sale_price") or product.get("unit_price"))
                    weight = _safe_float(product.get("unit_weight"))
                    thc = _safe_float(product.get("total_thc"))
                    cbd = _safe_float(product.get("total_cbd"))
                    batch_id = str(product.get("batch_num") or product.get("id") or "unknown")

                    # Flowery: terpenes are a flat dict {myrcene: 0.824, ...}
                    # Filter out "total" key — it's the sum, not an individual terpene
                    terps = product.get("terpenes")
                    if isinstance(terps, dict):
                        terpene_profile = {
                            k: _safe_float(v)
                            for k, v in terps.items()
                            if _safe_float(v) is not None and _safe_float(v) > 0
                            and k.lower() not in _TERPENE_SKIP_KEYS
                        }

                # ---------------------------------------------------------
                # Generic fallback for any field not yet set
                # ---------------------------------------------------------
                if not strain:
                    strain = self._extract_field(product, [
                        "strain", "strainName", "strain_name", "name", "productName", "title"
                    ]) or "Unknown"

                if not batch_id:
                    batch_id = self._extract_field(product, [
                        "batch_number", "batchNumber", "batchId", "batch_id", "batch_num",
                        "sku", "id"
                    ]) or "unknown"

                if not category:
                    category = self._extract_field(product, [
                        "category", "categories", "productCategory", "product_category", "type"
                    ]) or "unknown"

                if not product_name:
                    product_name = self._extract_field(product, [
                        "name", "productName", "product_name", "title"
                    ]) or strain

                strain_slug = self.normalize_strain_name(strain)
                item_id = hashlib.md5(
                    f"{dispensary}:{store.store_id}:{strain_slug}:{batch_id}".encode()
                ).hexdigest()[:12]

                # Generic fallbacks for cannabinoids/price/weight (if not set above)
                if thc is None:
                    thc = _safe_float(product.get("thc") or product.get("thcPercent") or product.get("thc_percent") or product.get("total_thc"))
                if cbd is None:
                    cbd = _safe_float(product.get("cbd") or product.get("cbdPercent") or product.get("cbd_percent") or product.get("total_cbd"))
                if price is None:
                    price = _safe_float(product.get("price") or product.get("unit_price") or product.get("sale_price"))
                if weight is None:
                    weight = _safe_float(product.get("weight") or product.get("weightGrams") or product.get("weight_grams") or product.get("unit_weight"))

                # Generic terpene profile fallback
                if not terpene_profile:
                    menu_terpenes = product.get("terpenes")
                    if isinstance(menu_terpenes, dict):
                        terpene_profile = {
                            k: _safe_float(v) for k, v in menu_terpenes.items()
                            if _safe_float(v) is not None
                            and k.lower() not in _TERPENE_SKIP_KEYS
                        }

                if not strain_type:
                    strain_type = product.get("strain_type") or product.get("strainType") or None
                if strain_type:
                    strain_type = strain_type.lower()

                ppg = None
                if price and weight and weight > 0:
                    ppg = round(price / weight, 2)

                item = StockItemV2(
                    id=item_id,
                    strain=strain,
                    strain_slug=strain_slug,
                    product_name=product_name,
                    dispensary=dispensary,
                    dispensary_name=DISPENSARY_NAMES.get(dispensary, dispensary.title()),
                    category=self._normalize_category(str(category)),
                    batch_id=str(batch_id),
                    store=store,
                    cannabinoids=Cannabinoids(thc_percent=thc, cbd_percent=cbd),
                    terpenes=TerpeneProfile(
                        profile=terpene_profile,
                        top_3=sorted(terpene_profile, key=terpene_profile.get, reverse=True)[:3] if terpene_profile else [],
                    ),
                    genetics=GeneticsInfo(strain_type=strain_type),
                    pricing=PricingInfo(price=price, weight_grams=weight, price_per_gram=ppg),
                    availability=AvailabilityInfo(
                        in_stock=True,
                        first_seen=now_iso,
                        last_seen=now_iso,
                        confidence="medium",
                    ),
                    source="menu",
                    source_file=blob_name,
                )

                # Generate links
                item.links = {
                    "terprint_web": f"https://terprint.acidni.net/strains/{strain_slug}",
                    "dispensary_page": f"https://terprint.acidni.net/dispensaries/{dispensary}",
                }
                if batch_id and batch_id != "unknown":
                    item.links["batch_detail"] = f"https://terprint.acidni.net/batches/{batch_id}"

                # Skip entries with generic/bogus strain names (e.g., Sweed POS
                # page headings captured by HTML fallback when a product 404s)
                _BOGUS_STRAIN_NAMES = {
                    "all products", "menu", "home", "shop", "products",
                    "category", "categories", "unknown",
                }
                if strain_slug in _BOGUS_STRAIN_NAMES or strain.lower() in _BOGUS_STRAIN_NAMES:
                    logger.debug(f"Skipping bogus strain name '{strain}' from {blob_name}")
                    continue

                items.append(item)

            logger.info(f"Extracted {len(items)} items from {blob_name}")
            return items

        except Exception as e:
            logger.error(f"Error processing menu file {blob_name}: {e}")
            return []

    @staticmethod
    def _extract_products(data: Any) -> list:
        """Extract product array from various menu JSON formats.

        Handles:
        - Direct list: [{...}, {...}]
        - Keyed: {products: [{...}]}
        - Nested: {data: {products: [{...}]}}  (Curaleaf, Flowery)
        - Double-nested: {data: {products: {list: [{...}]}}}  (MUV)
        """
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("products", "data", "items", "menu", "results"):
                val = data.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict):
                    for sub_key in ("products", "items", "results", "list"):
                        sub = val.get(sub_key)
                        if isinstance(sub, list):
                            return sub
                    # One more level: {data: {products: {list: [...]}}}
                    for sub_key in ("products", "items", "results"):
                        sub = val.get(sub_key)
                        if isinstance(sub, dict):
                            for deep_key in ("list", "items", "results"):
                                deep = sub.get(deep_key)
                                if isinstance(deep, list):
                                    return deep
        return []

    @staticmethod
    def _extract_field(product: dict, field_names: list[str]) -> str | None:
        """Extract a field trying multiple possible key names.

        Handles nested objects (MUV/Flowery: strain={name: ...})
        and array values (Flowery: categories=["Concentrates", "Solventless"]).
        """
        for name in field_names:
            val = product.get(name)
            if val is None:
                continue
            # Nested dict with 'name' key (e.g. strain: {name: "Blue Dream"})
            if isinstance(val, dict):
                inner = val.get("name") or val.get("title") or val.get("label")
                if inner:
                    return str(inner).strip()
                # Fallback: skip dicts without a name key
                continue
            # Array — take the first element (e.g. categories: ["Flower", "Roll-On"])
            if isinstance(val, list):
                for elem in val:
                    if isinstance(elem, dict):
                        inner = elem.get("name") or elem.get("title") or elem.get("label")
                        if inner:
                            return str(inner).strip()
                    elif elem:
                        return str(elem).strip()
                continue
            if val:
                return str(val).strip()
        return None

    @staticmethod
    def _normalize_category(category: str) -> str:
        """Normalize product category to standard values."""
        cat = category.lower().strip()
        mapping = {
            "flower": "Flower", "flowers": "Flower", "bud": "Flower",
            "whole flower": "Flower", "ground flower": "Flower", "ground": "Flower",
            "pre-roll": "Pre-Rolls", "pre-rolls": "Pre-Rolls", "preroll": "Pre-Rolls",
            "prerolls": "Pre-Rolls", "pre roll": "Pre-Rolls", "pre rolls": "Pre-Rolls",
            "joint": "Pre-Rolls", "joints": "Pre-Rolls", "infused pre-roll": "Pre-Rolls",
            "vape": "Vape", "vapes": "Vape", "cartridge": "Vape", "cartridges": "Vape",
            "cart": "Vape", "carts": "Vape", "pod": "Vape", "pods": "Vape",
            "510 cartridge": "Vape", "510 thread": "Vape", "disposable": "Vape",
            "concentrate": "Concentrates", "concentrates": "Concentrates",
            "extract": "Concentrates", "extracts": "Concentrates",
            "wax": "Concentrates", "shatter": "Concentrates", "rosin": "Concentrates",
            "live resin": "Concentrates", "live rosin": "Concentrates",
            "solventless": "Concentrates", "badder": "Concentrates", "budder": "Concentrates",
            "crumble": "Concentrates", "sauce": "Concentrates", "diamonds": "Concentrates",
            "distillate": "Concentrates", "hash": "Concentrates",
            "edible": "Edibles", "edibles": "Edibles",
            "gummy": "Edibles", "gummies": "Edibles", "chocolate": "Edibles",
            "topical": "Topicals", "topicals": "Topicals",
            "cream": "Topicals", "lotion": "Topicals", "balm": "Topicals",
            "tincture": "Tinctures", "tinctures": "Tinctures",
            "oral": "Tinctures", "sublingual": "Tinctures", "drops": "Tinctures",
            "capsule": "Capsules", "capsules": "Capsules",
            "rso": "RSO", "rick simpson": "RSO",
            "syringe": "Syringes", "syringes": "Syringes",
            "accessories": "Accessories", "accessory": "Accessories",
        }
        return mapping.get(cat, category.title() if category and category != "unknown" else "Other")

    # =========================================================================
    # Index Building — Main Entry Point
    # =========================================================================

    def build_index(self, max_age_days: int = 7) -> dict:
        """
        Build the full v2 stock index.

        Steps:
            1. Collect items from ALL dispensary menu files
            2. Load SQL enrichment data (optional fallback)
            3. Merge SQL enrichment onto menu items
            4. Enrich with genetics data
            5. Compute freshness scores
            6. Build index structures
        """
        logger.info("=== Stock Index v2 Build Starting ===")

        # Step 1: Collect from all dispensary menus
        all_items: list[StockItemV2] = []
        source_files: list[str] = []

        for dispensary in EXPECTED_DISPENSARIES:
            blobs = self._find_latest_menu_blobs(dispensary)
            if not blobs:
                continue

            # Process ALL blobs for this dispensary (one per store)
            for blob in blobs:
                items = self._process_menu_blob(blob.name, dispensary)
                all_items.extend(items)
                source_files.append(blob.name)

        logger.info(f"Menu scan: {len(all_items)} items from {len(source_files)} dispensary files")

        # Step 2: SQL enrichment
        sql_data = self._load_sql_enrichment(max_age_days)

        # Step 3: Merge SQL onto menu items
        enriched_count = 0
        for item in all_items:
            key = f"{item.dispensary}:{item.strain_slug}"
            sql_row = sql_data.get(key)
            if sql_row:
                self._apply_sql_enrichment(item, sql_row)
                enriched_count += 1

        logger.info(f"SQL enrichment applied to {enriched_count}/{len(all_items)} items")

        # Also add SQL-only items not found in menus (recently in stock in DB but not in latest menu)
        menu_keys = {f"{item.dispensary}:{item.strain_slug}" for item in all_items}
        sql_only_count = 0
        for key, row in sql_data.items():
            if key not in menu_keys:
                dispensary = (row.get("Dispensary") or "").lower()
                strain = row.get("Strain", "Unknown")
                strain_slug = self.normalize_strain_name(strain)
                store_loc = row.get("StoreLocation", "")
                store = self._resolve_store(dispensary, store_loc)

                item_id = hashlib.md5(f"{key}:{row.get('BatchId', '')}".encode()).hexdigest()[:12]

                item = StockItemV2(
                    id=item_id,
                    strain=strain,
                    strain_slug=strain_slug,
                    product_name=row.get("ProductName") or strain,
                    dispensary=dispensary,
                    dispensary_name=DISPENSARY_NAMES.get(dispensary, dispensary.title()),
                    category=self._normalize_category(row.get("Category") or "unknown"),
                    batch_id=row.get("BatchId", ""),
                    store=store,
                    source="database",
                )
                self._apply_sql_enrichment(item, row)
                all_items.append(item)
                sql_only_count += 1

        if sql_only_count:
            logger.info(f"Added {sql_only_count} SQL-only items not in menus")

        # Step 4: Genetics enrichment
        genetics_enriched = 0
        # Collect unique strain slugs to batch partition loading
        slug_partitions: dict[str, str] = {}
        genetics_index = self._load_genetics_index()
        for item in all_items:
            if item.strain_slug in genetics_index:
                info = genetics_index[item.strain_slug]
                slug_partitions[item.strain_slug] = info.get("partition", "other")

        # Load needed partitions
        loaded_partitions: dict[str, dict[str, dict]] = {}
        for partition_key in set(slug_partitions.values()):
            loaded_partitions[partition_key] = self._load_genetics_partition(partition_key)

        # Apply genetics
        for item in all_items:
            if item.strain_slug in genetics_index:
                info = genetics_index[item.strain_slug]
                item.genetics.strain_type = item.genetics.strain_type or info.get("type")
                item.genetics.has_full_genetics = info.get("has_lineage", False)

                if info.get("has_lineage"):
                    pk = slug_partitions.get(item.strain_slug, "other")
                    full = loaded_partitions.get(pk, {}).get(item.strain_slug)
                    if full:
                        item.genetics.parent_1 = full.get("parent_1")
                        item.genetics.parent_2 = full.get("parent_2")

                genetics_enriched += 1

        logger.info(f"Genetics enrichment applied to {genetics_enriched} items")

        # Step 5: Compute freshness
        now = datetime.now(timezone.utc)
        for item in all_items:
            if item.availability.last_seen:
                try:
                    seen_str = item.availability.last_seen.replace("Z", "+00:00")
                    seen = datetime.fromisoformat(seen_str)
                    if seen.tzinfo is None:
                        seen = seen.replace(tzinfo=timezone.utc)
                    delta = now - seen
                    item.availability.freshness_hours = round(delta.total_seconds() / 3600, 1)
                except Exception:
                    pass

        # Step 6: Build index
        logger.info(f"Building index from {len(all_items)} total items...")
        return self._build_full_index(all_items, source_files)

    # =========================================================================
    # Index Structures
    # =========================================================================

    def _build_full_index(self, items: list[StockItemV2], source_files: list[str]) -> dict:
        """Build the complete index structure with all groupings."""

        # Dedup: same dispensary + strain_slug + store_id → keep first
        seen_keys: set[str] = set()
        deduped: list[StockItemV2] = []
        for item in items:
            key = f"{item.dispensary}:{item.strain_slug}:{item.store.store_id}"
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(item)

        items = sorted(deduped, key=lambda x: (x.strain_slug, x.dispensary))
        logger.info(f"After dedup: {len(items)} unique items")

        by_strain: dict[str, list[dict]] = defaultdict(list)
        by_dispensary: dict[str, list[dict]] = defaultdict(list)
        by_category: dict[str, list[dict]] = defaultdict(list)
        by_store: dict[str, list[dict]] = defaultdict(list)

        items_dicts = []
        for item in items:
            d = asdict(item)
            items_dicts.append(d)
            by_strain[item.strain_slug].append(d)
            by_dispensary[item.dispensary].append(d)
            by_category[item.category].append(d)
            by_store[item.store.store_id].append(d)

        # Dispensary stats
        dispensary_stats = {}
        for disp, disp_items in by_dispensary.items():
            stores = {it.get("store", {}).get("store_id", "") for it in disp_items}
            freshest = min(
                (it.get("availability", {}).get("freshness_hours") for it in disp_items
                 if it.get("availability", {}).get("freshness_hours") is not None),
                default=None,
            )
            dispensary_stats[disp] = {
                "count": len(disp_items),
                "stores": len(stores),
                "freshest_hours": freshest,
            }

        # Category stats
        category_stats = [
            {"category": cat, "count": len(cat_items)}
            for cat, cat_items in sorted(by_category.items(), key=lambda x: -len(x[1]))
        ]

        # Top strains
        top_strains = sorted(by_strain.items(), key=lambda x: -len(x[1]))[:20]
        top_strains_list = []
        for slug, strain_items in top_strains:
            thc_vals = [
                it.get("cannabinoids", {}).get("thc_percent")
                for it in strain_items
                if it.get("cannabinoids", {}).get("thc_percent") is not None
            ]
            avg_thc = round(sum(thc_vals) / len(thc_vals), 1) if thc_vals else None
            disps = list({it.get("dispensary", "") for it in strain_items})
            stores = list({it.get("store", {}).get("store_id", "") for it in strain_items})
            top_strains_list.append({
                "strain": strain_items[0].get("strain", slug),
                "slug": slug,
                "dispensaries": disps,
                "store_count": len(stores),
                "avg_thc": avg_thc,
            })

        # Freshness buckets
        freshness = {"under_2h": 0, "under_6h": 0, "under_24h": 0, "over_24h": 0}
        for item in items:
            h = item.availability.freshness_hours
            if h is None:
                freshness["over_24h"] += 1
            elif h < 2:
                freshness["under_2h"] += 1
            elif h < 6:
                freshness["under_6h"] += 1
            elif h < 24:
                freshness["under_24h"] += 1
            else:
                freshness["over_24h"] += 1

        # Enrichment stats
        with_coa = sum(1 for it in items if it.cannabinoids.thc_percent is not None)
        with_terpenes = sum(1 for it in items if it.terpenes.profile)
        with_genetics = sum(1 for it in items if it.genetics.strain_type is not None)
        with_location = sum(1 for it in items if it.store.latitude is not None)

        metadata = {
            "version": "2.0.0",
            "build_date": datetime.now(timezone.utc).isoformat(),
            "total_items": len(items),
            "unique_strains": len(by_strain),
            "dispensaries": dispensary_stats,
            "categories": category_stats,
            "source_files": source_files,
            "enrichment": {
                "with_coa": with_coa,
                "with_terpenes": with_terpenes,
                "with_genetics": with_genetics,
                "with_location": with_location,
            },
            "freshness": freshness,
        }

        # Summary (lightweight)
        summary = {
            "version": "2.0.0",
            "updated": metadata["build_date"],
            "totals": {
                "products_in_stock": len(items),
                "unique_strains": len(by_strain),
                "dispensaries": len(by_dispensary),
                "stores": len(by_store),
                "with_coa": with_coa,
                "with_terpenes": with_terpenes,
                "with_genetics": with_genetics,
                "with_location": with_location,
            },
            "by_dispensary": [
                {"name": DISPENSARY_NAMES.get(d, d), "slug": d, **stats}
                for d, stats in sorted(dispensary_stats.items(), key=lambda x: -x[1]["count"])
            ],
            "by_category": category_stats,
            "top_strains": top_strains_list[:10],
            "freshness": freshness,
        }

        index = {
            "metadata": metadata,
            "summary": summary,
            "items": items_dicts,
            "by_strain": dict(by_strain),
            "by_dispensary": dict(by_dispensary),
            "by_category": dict(by_category),
        }

        # Store partitioned data for upload
        index["_by_store"] = dict(by_store)
        index["_by_dispensary_files"] = {
            disp: disp_items for disp, disp_items in by_dispensary.items()
        }

        logger.info(
            f"Index built: {len(items)} items, {len(by_strain)} strains, "
            f"{len(by_dispensary)} dispensaries, {len(by_store)} stores"
        )
        return index

    # =========================================================================
    # Save / Load
    # =========================================================================

    def save_index(self, index: dict) -> str:
        """
        Save v2 index with partitioned files.

        Outputs:
            stock-index/current.json         Full index (items + by_strain + by_dispensary)
            stock-index/summary.json         Lightweight dashboard data
            stock-index/metadata.json        Build metadata
            stock-index/by-dispensary/{x}.json   Per-dispensary files
            stock-index/by-store/{x}.json        Per-store files
        """
        container = self._get_blob_container()
        if not container:
            logger.error("Cannot save index — blob container unavailable")
            return ""

        prefix = self.INDEX_PREFIX
        saved_paths = []

        # --- current.json (full index without internal partition data) ---
        export = {
            "metadata": index["metadata"],
            "summary": index["summary"],
            "items": index["items"],
            "by_strain": index["by_strain"],
            "by_dispensary": index["by_dispensary"],
            "by_category": index["by_category"],
        }
        self._upload_json(container, f"{prefix}/current.json", export)
        saved_paths.append(f"{prefix}/current.json")

        # --- summary.json ---
        self._upload_json(container, f"{prefix}/summary.json", index["summary"])
        saved_paths.append(f"{prefix}/summary.json")

        # --- metadata.json ---
        self._upload_json(container, f"{prefix}/metadata.json", index["metadata"])
        saved_paths.append(f"{prefix}/metadata.json")

        # --- Per-dispensary files ---
        for disp, disp_items in index.get("_by_dispensary_files", {}).items():
            path = f"{prefix}/by-dispensary/{disp}.json"
            self._upload_json(container, path, {
                "dispensary": disp,
                "dispensary_name": DISPENSARY_NAMES.get(disp, disp.title()),
                "total_items": len(disp_items),
                "updated": index["metadata"]["build_date"],
                "items": disp_items,
            })
            saved_paths.append(path)

        # --- Per-store files ---
        for store_id, store_items in index.get("_by_store", {}).items():
            # Sanitize store_id for blob path
            safe_id = re.sub(r"[^a-z0-9\-]", "-", store_id.lower()).strip("-")
            if not safe_id:
                continue
            path = f"{prefix}/by-store/{safe_id}.json"
            self._upload_json(container, path, {
                "store_id": store_id,
                "total_items": len(store_items),
                "updated": index["metadata"]["build_date"],
                "items": store_items,
            })
            saved_paths.append(path)

        # --- Timestamp ---
        ts_blob = container.get_blob_client(f"{prefix}/last_updated.txt")
        ts_blob.upload_blob(datetime.now(timezone.utc).isoformat(), overwrite=True)

        # --- Availability History Tracking ---
        try:
            tracker = StockAvailabilityTracker(container, prefix)
            tracker_result = tracker.update(index.get("items", []))
            logger.info(
                f"Availability tracker: {tracker_result.get('new_arrivals', 0)} new, "
                f"{tracker_result.get('went_out_of_stock', 0)} disappeared, "
                f"{tracker_result.get('still_in_stock', 0)} still here"
            )

            # --- Persistent Stock Ledger (Cosmos DB) ---
            try:
                appeared = tracker_result.get("_appeared_items", {})
                disappeared = tracker_result.get("_disappeared_items", {})
                restocked = tracker_result.get("_restocked_items", {})
                if appeared or disappeared or restocked:
                    build_id = f"stock-build-{index['metadata']['build_date']}"
                    ledger = StockLedgerWriter()
                    ledger_result = ledger.write_events(
                        appeared=appeared,
                        disappeared=disappeared,
                        restocked=restocked,
                        build_id=build_id,
                    )
                    logger.info(
                        f"Stock ledger: {ledger_result.get('written', 0)} events persisted "
                        f"(a={ledger_result.get('appeared', 0)}, "
                        f"d={ledger_result.get('disappeared', 0)}, "
                        f"r={ledger_result.get('restocked', 0)})"
                    )
                else:
                    logger.info("Stock ledger: no changes to persist")
            except Exception as e:
                logger.warning(f"Stock ledger write failed (non-fatal): {e}")

        except Exception as e:
            logger.warning(f"Availability tracker failed (non-fatal): {e}")

        logger.info(f"Saved {len(saved_paths)} index files to blob storage")
        return f"{prefix}/current.json"

    def get_index(self) -> dict | None:
        """Load current stock index from blob storage."""
        try:
            container = self._get_blob_container()
            if not container:
                return None
            blob = container.get_blob_client(f"{self.INDEX_PREFIX}/current.json")
            content = blob.download_blob().readall()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load stock index: {e}")
            return None

    def get_summary(self) -> dict | None:
        """Load lightweight summary from blob storage."""
        try:
            container = self._get_blob_container()
            if not container:
                return None
            blob = container.get_blob_client(f"{self.INDEX_PREFIX}/summary.json")
            content = blob.download_blob().readall()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load stock summary: {e}")
            return None

    @staticmethod
    def _upload_json(container, path: str, data: dict) -> None:
        """Upload JSON to blob storage."""
        blob = container.get_blob_client(path)
        blob.upload_blob(json.dumps(data, indent=2, default=str), overwrite=True)
        logger.debug(f"Uploaded {path}")

    # =========================================================================
    # Utilities
    # =========================================================================

    @staticmethod
    def normalize_strain_name(strain: str) -> str:
        """Normalize strain name to slug format for consistent indexing."""
        if not strain:
            return "unknown"
        slug = strain.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        return slug.strip("-") or "unknown"

    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine distance in miles."""
        import math

        R = 3959
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =============================================================================
# Stock Availability Tracker — Lifecycle History
# =============================================================================

class StockAvailabilityTracker:
    """
    Tracks stock lifecycle events: appeared, disappeared, restocked.

    Runs as part of every stock index build. Diffs current items against
    previous state to detect:
      - New arrivals (first_seen_at = now)
      - Items gone out of stock (went_out_of_stock_at = now)
      - Restocks (appeared again after disappearing)

    Produces:
      - stock-index/availability-history.json  (full lifecycle state)
      - stock-index/hot-products.json          (derived analytics)
    """

    HISTORY_BLOB = "availability-history.json"
    HOT_PRODUCTS_BLOB = "hot-products.json"
    # Keep history entries for items out of stock up to this many days
    MAX_OUT_OF_STOCK_DAYS = 90
    # Max history events per item (to prevent unbounded growth)
    MAX_HISTORY_EVENTS = 50

    def __init__(self, blob_container, prefix: str = "stock-index"):
        self._container = blob_container
        self._prefix = prefix

    # -----------------------------------------------------------------
    # Blob I/O
    # -----------------------------------------------------------------

    def _load_history(self) -> dict:
        """Load previous availability history from blob storage."""
        try:
            blob = self._container.get_blob_client(
                f"{self._prefix}/{self.HISTORY_BLOB}"
            )
            content = blob.download_blob().readall()
            return json.loads(content)
        except Exception:
            logger.info("No previous availability history found — starting fresh")
            return {"version": "1.0.0", "tracking_since": None, "items": {}}

    def _save_history(self, history: dict) -> None:
        """Save availability history to blob storage."""
        blob = self._container.get_blob_client(
            f"{self._prefix}/{self.HISTORY_BLOB}"
        )
        blob.upload_blob(
            json.dumps(history, indent=2, default=str), overwrite=True
        )

    def _save_hot_products(self, analytics: dict) -> None:
        """Save hot-products analytics to blob storage."""
        blob = self._container.get_blob_client(
            f"{self._prefix}/{self.HOT_PRODUCTS_BLOB}"
        )
        blob.upload_blob(
            json.dumps(analytics, indent=2, default=str), overwrite=True
        )

    def get_history(self) -> dict | None:
        """Public accessor — load availability history."""
        try:
            return self._load_history()
        except Exception:
            return None

    def get_hot_products(self) -> dict | None:
        """Public accessor — load hot-products analytics."""
        try:
            blob = self._container.get_blob_client(
                f"{self._prefix}/{self.HOT_PRODUCTS_BLOB}"
            )
            content = blob.download_blob().readall()
            return json.loads(content)
        except Exception:
            return None

    # -----------------------------------------------------------------
    # Core Diff Algorithm
    # -----------------------------------------------------------------

    def update(self, current_items_dicts: list[dict]) -> dict:
        """
        Diff current stock items against previous state and update history.

        Args:
            current_items_dicts: List of stock item dicts from the current build.

        Returns:
            Summary dict with counts of new, disappeared, still-here items.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        previous = self._load_history()
        prev_items: dict = previous.get("items", {})
        tracking_since = previous.get("tracking_since") or now_iso

        # Build current keyed set: key = dispensary:strain_slug:store_id
        current_keyed: dict[str, dict] = {}
        for item in current_items_dicts:
            store = item.get("store", {})
            key = (
                f"{item.get('dispensary', '')}:"
                f"{item.get('strain_slug', '')}:"
                f"{store.get('store_id', '')}"
            )
            # Keep the item with the most data (first occurrence is fine since
            # items are already deduped by the index builder)
            if key not in current_keyed:
                current_keyed[key] = item

        current_keys = set(current_keyed.keys())
        previous_keys = set(prev_items.keys())

        appeared_keys = current_keys - previous_keys
        disappeared_keys = previous_keys - current_keys
        still_here_keys = current_keys & previous_keys

        # --- Process NEW arrivals ---
        for key in appeared_keys:
            item = current_keyed[key]
            prev_items[key] = {
                "strain": item.get("strain", ""),
                "strain_slug": item.get("strain_slug", ""),
                "dispensary": item.get("dispensary", ""),
                "dispensary_name": item.get("dispensary_name", ""),
                "store_id": item.get("store", {}).get("store_id", ""),
                "store_name": item.get("store", {}).get("store_name", ""),
                "category": item.get("category", ""),
                "product_name": item.get("product_name", ""),
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
                "went_out_of_stock_at": None,
                "in_stock": True,
                "times_restocked": 0,
                "history": [{"event": "appeared", "at": now_iso}],
            }

        # --- Process items STILL in stock ---
        for key in still_here_keys:
            entry = prev_items[key]
            entry["last_seen_at"] = now_iso
            entry["in_stock"] = True
            entry["went_out_of_stock_at"] = None
            # Update product info from current build (may have new price/name)
            item = current_keyed[key]
            entry["product_name"] = item.get("product_name", entry.get("product_name", ""))
            entry["category"] = item.get("category", entry.get("category", ""))

        # --- Process items that DISAPPEARED ---
        for key in disappeared_keys:
            entry = prev_items[key]
            if entry.get("in_stock", True):
                # Transition: in_stock → out_of_stock
                entry["in_stock"] = False
                entry["went_out_of_stock_at"] = now_iso
                history = entry.get("history", [])
                history.append({"event": "disappeared", "at": now_iso})
                # Cap history length
                if len(history) > self.MAX_HISTORY_EVENTS:
                    history = history[-self.MAX_HISTORY_EVENTS:]
                entry["history"] = history

        # --- Detect RESTOCKS (was out of stock, now back) ---
        # These appear in appeared_keys BUT may have a previous entry that was
        # marked out-of-stock.  We already handled appeared_keys above as new,
        # but we need to check if there was a *previous* entry with same key
        # that was out-of-stock.
        # Actually, if the key is in appeared_keys it is NOT in previous_keys,
        # so restocks must be detected differently.
        # A restock happens when an item *was* in prev_items with in_stock=False
        # and now appears in current_keyed.  Let's check: since appeared_keys
        # = current - previous, items that were *previously tracked but removed*
        # won't be in previous_keys anymore unless they were kept.
        # They ARE kept because we don't purge immediately — we just set
        # in_stock=False.  So restocks show up in still_here_keys (they're in
        # both prev and current) where prev entry has in_stock=False.
        restocked_count = 0
        for key in still_here_keys:
            entry = prev_items[key]
            # If prev state was out of stock but now it's back
            if not entry.get("_was_in_stock", True):
                entry["times_restocked"] = entry.get("times_restocked", 0) + 1
                entry["went_out_of_stock_at"] = None
                history = entry.get("history", [])
                history.append({"event": "restocked", "at": now_iso})
                if len(history) > self.MAX_HISTORY_EVENTS:
                    history = history[-self.MAX_HISTORY_EVENTS:]
                entry["history"] = history
                restocked_count += 1
            # Stash current in_stock state for next run's restock detection
            entry["_was_in_stock"] = True

        for key in disappeared_keys:
            entry = prev_items[key]
            entry["_was_in_stock"] = False

        # --- Compute days_in_stock ---
        for key, entry in prev_items.items():
            first = entry.get("first_seen_at")
            if first and entry.get("in_stock"):
                try:
                    first_dt = datetime.fromisoformat(
                        first.replace("Z", "+00:00")
                    )
                    if first_dt.tzinfo is None:
                        first_dt = first_dt.replace(tzinfo=timezone.utc)
                    entry["days_in_stock"] = round(
                        (now - first_dt).total_seconds() / 86400, 1
                    )
                except Exception:
                    entry["days_in_stock"] = None
            elif not entry.get("in_stock"):
                # Calculate how long it WAS in stock before disappearing
                first = entry.get("first_seen_at")
                out_at = entry.get("went_out_of_stock_at")
                if first and out_at:
                    try:
                        first_dt = datetime.fromisoformat(
                            first.replace("Z", "+00:00")
                        )
                        out_dt = datetime.fromisoformat(
                            out_at.replace("Z", "+00:00")
                        )
                        if first_dt.tzinfo is None:
                            first_dt = first_dt.replace(tzinfo=timezone.utc)
                        if out_dt.tzinfo is None:
                            out_dt = out_dt.replace(tzinfo=timezone.utc)
                        entry["days_in_stock"] = round(
                            (out_dt - first_dt).total_seconds() / 86400, 1
                        )
                    except Exception:
                        pass

        # --- Purge very old out-of-stock entries ---
        cutoff = now - timedelta(days=self.MAX_OUT_OF_STOCK_DAYS)
        purge_keys = []
        for key, entry in prev_items.items():
            if not entry.get("in_stock"):
                out_at = entry.get("went_out_of_stock_at")
                if out_at:
                    try:
                        out_dt = datetime.fromisoformat(
                            out_at.replace("Z", "+00:00")
                        )
                        if out_dt.tzinfo is None:
                            out_dt = out_dt.replace(tzinfo=timezone.utc)
                        if out_dt < cutoff:
                            purge_keys.append(key)
                    except Exception:
                        pass
        for key in purge_keys:
            del prev_items[key]

        # --- Build updated history blob ---
        in_stock_count = sum(
            1 for e in prev_items.values() if e.get("in_stock")
        )
        out_of_stock_count = sum(
            1 for e in prev_items.values() if not e.get("in_stock")
        )

        history_output = {
            "version": "1.0.0",
            "updated_at": now_iso,
            "tracking_since": tracking_since,
            "total_tracked": len(prev_items),
            "currently_in_stock": in_stock_count,
            "out_of_stock": out_of_stock_count,
            "purged_old_entries": len(purge_keys),
            "items": prev_items,
        }

        self._save_history(history_output)
        logger.info(
            f"Availability history saved: {len(prev_items)} tracked, "
            f"{in_stock_count} in stock, {out_of_stock_count} out"
        )

        # --- Build hot-products analytics ---
        analytics = self._compute_analytics(prev_items, now)
        self._save_hot_products(analytics)
        logger.info(
            f"Hot products saved: {len(analytics.get('fastest_sellers', []))} hot, "
            f"{len(analytics.get('new_arrivals', []))} new, "
            f"{len(analytics.get('recently_sold_out', []))} sold out"
        )

        # --- Collect restocked items for ledger ---
        restocked_items = {}
        for key in still_here_keys:
            entry = prev_items[key]
            if entry.get("times_restocked", 0) > 0:
                # Check if this is a NEW restock from this run
                hist = entry.get("history", [])
                if hist and hist[-1].get("event") == "restocked" and hist[-1].get("at") == now_iso:
                    restocked_items[key] = current_keyed.get(key, entry)

        return {
            "new_arrivals": len(appeared_keys),
            "went_out_of_stock": len(disappeared_keys),
            "still_in_stock": len(still_here_keys),
            "restocked": restocked_count,
            "purged": len(purge_keys),
            "total_tracked": len(prev_items),
            # Diff data for persistent ledger
            "_appeared_items": {k: current_keyed[k] for k in appeared_keys},
            "_disappeared_items": {k: prev_items[k] for k in disappeared_keys if k in prev_items},
            "_restocked_items": restocked_items,
        }

    # -----------------------------------------------------------------
    # Analytics Computation
    # -----------------------------------------------------------------

    def _compute_analytics(self, items: dict, now: datetime) -> dict:
        """Compute hot-products analytics from availability history."""
        new_arrivals = []
        fastest_sellers = []
        long_stayers = []
        recently_sold_out = []
        gaining_stores: dict[str, dict] = {}
        losing_stores: dict[str, dict] = {}

        for key, entry in items.items():
            strain = entry.get("strain", "")
            strain_slug = entry.get("strain_slug", "")
            dispensary = entry.get("dispensary", "")
            dispensary_name = entry.get("dispensary_name", "")
            category = entry.get("category", "")
            in_stock = entry.get("in_stock", False)
            first_seen = entry.get("first_seen_at")
            days = entry.get("days_in_stock")
            times_restocked = entry.get("times_restocked", 0)
            store_name = entry.get("store_name", "")

            # --- New arrivals: first seen in last 72 hours ---
            if in_stock and first_seen:
                try:
                    fs_dt = datetime.fromisoformat(
                        first_seen.replace("Z", "+00:00")
                    )
                    if fs_dt.tzinfo is None:
                        fs_dt = fs_dt.replace(tzinfo=timezone.utc)
                    hours_ago = (now - fs_dt).total_seconds() / 3600
                    if hours_ago <= 72:
                        new_arrivals.append({
                            "strain": strain,
                            "strain_slug": strain_slug,
                            "dispensary": dispensary,
                            "dispensary_name": dispensary_name,
                            "store_name": store_name,
                            "category": category,
                            "first_seen_at": first_seen,
                            "hours_ago": round(hours_ago, 1),
                        })
                except Exception:
                    pass

            # --- Recently sold out: disappeared in last 48 hours ---
            if not in_stock:
                out_at = entry.get("went_out_of_stock_at")
                if out_at:
                    try:
                        out_dt = datetime.fromisoformat(
                            out_at.replace("Z", "+00:00")
                        )
                        if out_dt.tzinfo is None:
                            out_dt = out_dt.replace(tzinfo=timezone.utc)
                        hours_since = (now - out_dt).total_seconds() / 3600
                        if hours_since <= 48:
                            recently_sold_out.append({
                                "strain": strain,
                                "strain_slug": strain_slug,
                                "dispensary": dispensary,
                                "dispensary_name": dispensary_name,
                                "store_name": store_name,
                                "category": category,
                                "went_out_of_stock_at": out_at,
                                "was_in_stock_days": days,
                                "hours_since_sold_out": round(hours_since, 1),
                            })
                    except Exception:
                        pass

            # --- Long stayers: in stock > 14 days ---
            if in_stock and days is not None and days > 14:
                long_stayers.append({
                    "strain": strain,
                    "strain_slug": strain_slug,
                    "dispensary": dispensary,
                    "dispensary_name": dispensary_name,
                    "store_name": store_name,
                    "category": category,
                    "days_in_stock": days,
                    "first_seen_at": first_seen,
                })

            # --- Fast sellers: items that restock frequently OR spend
            #     very few days in stock ---
            if times_restocked >= 1 or (
                not in_stock and days is not None and days < 5
            ):
                # Compute hotness score
                avg_days = days if days else 999
                restock_factor = times_restocked * 30
                speed_factor = (1 / max(avg_days, 0.1)) * 40
                recency_bonus = 20 if times_restocked > 0 else 0
                hotness = round(restock_factor + speed_factor + recency_bonus, 1)

                fastest_sellers.append({
                    "strain": strain,
                    "strain_slug": strain_slug,
                    "dispensary": dispensary,
                    "dispensary_name": dispensary_name,
                    "category": category,
                    "avg_days_in_stock": days,
                    "times_restocked": times_restocked,
                    "hotness_score": hotness,
                })

        # --- Aggregate store counts per strain for trending ---
        # Group current in-stock items by strain_slug
        strain_store_counts: dict[str, set] = defaultdict(set)
        for key, entry in items.items():
            if entry.get("in_stock"):
                slug = entry.get("strain_slug", "")
                store_id = entry.get("store_id", "")
                if slug and store_id:
                    strain_store_counts[slug].add(store_id)

        # Sort and limit results
        new_arrivals.sort(key=lambda x: x.get("hours_ago", 999))
        new_arrivals = new_arrivals[:100]

        fastest_sellers.sort(
            key=lambda x: x.get("hotness_score", 0), reverse=True
        )
        fastest_sellers = fastest_sellers[:50]

        long_stayers.sort(
            key=lambda x: x.get("days_in_stock", 0), reverse=True
        )
        long_stayers = long_stayers[:50]

        recently_sold_out.sort(
            key=lambda x: x.get("hours_since_sold_out", 999)
        )
        recently_sold_out = recently_sold_out[:50]

        return {
            "version": "1.0.0",
            "updated_at": now.isoformat(),
            "period_note": "New arrivals=72h, sold out=48h, long stayers=14d+",
            "fastest_sellers": fastest_sellers,
            "new_arrivals": new_arrivals,
            "long_stayers": long_stayers,
            "recently_sold_out": recently_sold_out,
            "strain_store_counts": {
                slug: len(stores)
                for slug, stores in sorted(
                    strain_store_counts.items(),
                    key=lambda x: -len(x[1]),
                )[:30]
            },
        }


# =============================================================================
# Persistent Stock Ledger — Cosmos DB Event Log
# =============================================================================

class StockLedgerWriter:
    """
    Writes immutable stock lifecycle events to Cosmos DB for permanent history.

    Every time the StockAvailabilityTracker computes a diff (appeared,
    disappeared, restocked), the ledger writer persists those events as
    individual Cosmos DB documents. Unlike the blob-based availability-history
    (which purges after 90 days and caps at 50 events per item), the ledger
    is a permanent, queryable record.

    Cosmos DB container: TerprintAI / stock-ledger
    Partition key: /strain_slug

    Enables:
      - "When was Blue Dream last in stock at Trulieve Tampa?"
      - "Show me all stock events for Gorilla Glue #4"
      - "How often does MUV restock Wedding Cake?"
      - Price history over time for a strain
    """

    COSMOS_ACCOUNT = "https://cosmos-terprint-dev.documents.azure.com:443/"
    DATABASE_NAME = "TerprintAI"
    CONTAINER_NAME = "stock-ledger"

    def __init__(self):
        self._container = None

    def _get_container(self):
        """Get or create Cosmos DB container client using managed identity."""
        if self._container is not None:
            return self._container
        try:
            from azure.cosmos import CosmosClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            client = CosmosClient(self.COSMOS_ACCOUNT, credential=credential)
            db = client.get_database_client(self.DATABASE_NAME)
            self._container = db.get_container_client(self.CONTAINER_NAME)
            logger.info("Stock ledger Cosmos DB connection established")
            return self._container
        except Exception as e:
            logger.error(f"Failed to connect to stock ledger Cosmos DB: {e}")
            return None

    def write_events(
        self,
        appeared: dict[str, dict],
        disappeared: dict[str, dict],
        restocked: dict[str, dict],
        build_id: str,
    ) -> dict:
        """
        Write stock lifecycle events to Cosmos DB.

        Args:
            appeared: Dict of key -> item data for new arrivals
            disappeared: Dict of key -> item data for items that went OOS
            restocked: Dict of key -> item data for items that came back
            build_id: Unique identifier for this index build

        Returns:
            Summary dict with counts of events written
        """
        container = self._get_container()
        if container is None:
            logger.warning("Stock ledger unavailable — skipping event write")
            return {"written": 0, "errors": 0, "skipped": True}

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        written = 0
        errors = 0

        # --- Write APPEARED events ---
        for key, item in appeared.items():
            try:
                doc = self._build_event_doc(
                    event="appeared",
                    key=key,
                    item=item,
                    timestamp=now_iso,
                    build_id=build_id,
                )
                container.upsert_item(doc)
                written += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Ledger write failed for appeared {key}: {e}")

        # --- Write DISAPPEARED events ---
        for key, item in disappeared.items():
            try:
                doc = self._build_event_doc(
                    event="disappeared",
                    key=key,
                    item=item,
                    timestamp=now_iso,
                    build_id=build_id,
                )
                container.upsert_item(doc)
                written += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Ledger write failed for disappeared {key}: {e}")

        # --- Write RESTOCKED events ---
        for key, item in restocked.items():
            try:
                doc = self._build_event_doc(
                    event="restocked",
                    key=key,
                    item=item,
                    timestamp=now_iso,
                    build_id=build_id,
                )
                container.upsert_item(doc)
                written += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Ledger write failed for restocked {key}: {e}")

        logger.info(
            f"Stock ledger: {written} events written, {errors} errors "
            f"(appeared={len(appeared)}, disappeared={len(disappeared)}, "
            f"restocked={len(restocked)})"
        )

        return {
            "written": written,
            "errors": errors,
            "appeared": len(appeared),
            "disappeared": len(disappeared),
            "restocked": len(restocked),
            "build_id": build_id,
        }

    def _build_event_doc(
        self,
        event: str,
        key: str,
        item: dict,
        timestamp: str,
        build_id: str,
    ) -> dict:
        """Build a Cosmos DB document for a single stock event."""
        # Generate deterministic ID: event type + key + timestamp
        raw_id = f"{event}:{key}:{timestamp}"
        doc_id = hashlib.sha256(raw_id.encode()).hexdigest()[:24]

        # Extract fields from item (supports both current-index items and
        # tracker entries which have slightly different shapes)
        strain = item.get("strain", "")
        strain_slug = item.get("strain_slug", "")
        dispensary = item.get("dispensary", "")
        dispensary_name = item.get("dispensary_name", "")
        category = item.get("category", "")
        product_name = item.get("product_name", "")

        # Store info — may be nested dict (from index) or flat (from tracker)
        store = item.get("store", {})
        store_id = store.get("store_id", "") if isinstance(store, dict) else item.get("store_id", "")
        store_name = store.get("store_name", "") if isinstance(store, dict) else item.get("store_name", "")

        # Pricing — from index items
        pricing = item.get("pricing", {})
        price = pricing.get("price") if isinstance(pricing, dict) else item.get("price")
        weight_grams = pricing.get("weight_grams") if isinstance(pricing, dict) else item.get("weight_grams")

        # Cannabinoids — from index items
        cannabinoids = item.get("cannabinoids", {})
        thc_percent = cannabinoids.get("thc_percent") if isinstance(cannabinoids, dict) else item.get("thc_percent")

        # Terpenes — from index items
        terpenes = item.get("terpenes", {})
        terpene_total = terpenes.get("total_percent") if isinstance(terpenes, dict) else None
        top_terpenes = terpenes.get("top_3", []) if isinstance(terpenes, dict) else []

        # Batch
        batch_id = item.get("batch_id", "")

        return {
            "id": doc_id,
            "type": "stock_event",
            "event": event,
            "timestamp": timestamp,
            "strain_slug": strain_slug,
            "strain": strain,
            "dispensary": dispensary,
            "dispensary_name": dispensary_name,
            "store_id": store_id,
            "store_name": store_name,
            "product_name": product_name,
            "category": category,
            "batch_id": batch_id,
            "price": _safe_float(price),
            "weight_grams": _safe_float(weight_grams),
            "thc_percent": _safe_float(thc_percent),
            "terpene_total_percent": _safe_float(terpene_total),
            "top_terpenes": top_terpenes,
            "build_id": build_id,
            "item_key": key,
        }

    def query_strain_history(
        self,
        strain_slug: str,
        dispensary: str | None = None,
        store_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Query the full event history for a specific strain.

        Args:
            strain_slug: Strain identifier (partition key)
            dispensary: Optional dispensary filter
            store_id: Optional store filter
            event_type: Optional event type filter (appeared/disappeared/restocked)
            limit: Max results

        Returns:
            List of event documents, newest first
        """
        container = self._get_container()
        if container is None:
            return []

        conditions = ["c.strain_slug = @strain_slug"]
        params = [{"name": "@strain_slug", "value": strain_slug}]

        if dispensary:
            conditions.append("c.dispensary = @dispensary")
            params.append({"name": "@dispensary", "value": dispensary})
        if store_id:
            conditions.append("c.store_id = @store_id")
            params.append({"name": "@store_id", "value": store_id})
        if event_type:
            conditions.append("c.event = @event_type")
            params.append({"name": "@event_type", "value": event_type})

        query = (
            f"SELECT * FROM c WHERE {' AND '.join(conditions)} "
            f"ORDER BY c.timestamp DESC OFFSET 0 LIMIT {limit}"
        )

        try:
            results = list(
                container.query_items(
                    query=query,
                    parameters=params,
                    partition_key=strain_slug,
                )
            )
            return results
        except Exception as e:
            logger.error(f"Ledger query failed for {strain_slug}: {e}")
            return []

    def query_store_history(
        self,
        store_id: str,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Query all stock events at a specific store (cross-partition).

        Args:
            store_id: Store identifier
            event_type: Optional event filter
            limit: Max results

        Returns:
            List of event documents, newest first
        """
        container = self._get_container()
        if container is None:
            return []

        conditions = ["c.store_id = @store_id"]
        params = [{"name": "@store_id", "value": store_id}]

        if event_type:
            conditions.append("c.event = @event_type")
            params.append({"name": "@event_type", "value": event_type})

        query = (
            f"SELECT * FROM c WHERE {' AND '.join(conditions)} "
            f"ORDER BY c.timestamp DESC OFFSET 0 LIMIT {limit}"
        )

        try:
            results = list(
                container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True,
                )
            )
            return results
        except Exception as e:
            logger.error(f"Ledger query failed for store {store_id}: {e}")
            return []

    def query_recent_events(
        self,
        event_type: str | None = None,
        hours: int = 72,
        dispensary: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Query recent stock events across all strains (cross-partition).

        Args:
            event_type: Filter by event type (appeared/disappeared/restocked)
            hours: Look back this many hours
            dispensary: Optional dispensary filter
            limit: Max results

        Returns:
            List of event documents, newest first
        """
        container = self._get_container()
        if container is None:
            return []

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conditions = ["c.timestamp >= @cutoff"]
        params = [{"name": "@cutoff", "value": cutoff}]

        if event_type:
            conditions.append("c.event = @event_type")
            params.append({"name": "@event_type", "value": event_type})
        if dispensary:
            conditions.append("c.dispensary = @dispensary")
            params.append({"name": "@dispensary", "value": dispensary})

        query = (
            f"SELECT * FROM c WHERE {' AND '.join(conditions)} "
            f"ORDER BY c.timestamp DESC OFFSET 0 LIMIT {limit}"
        )

        try:
            results = list(
                container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True,
                )
            )
            return results
        except Exception as e:
            logger.error(f"Ledger recent events query failed: {e}")
            return []

    def get_strain_timeline(
        self,
        strain_slug: str,
        dispensary: str | None = None,
        store_id: str | None = None,
    ) -> list[dict]:
        """
        Build a condensed timeline showing in-stock/out-of-stock periods.

        Returns a list of period dicts:
        [
            {"store_id": "...", "store_name": "...", "dispensary": "...",
             "in_stock_from": "...", "out_of_stock_at": "...", "days_available": 5.2,
             "price": 43.0, "thc_percent": 24.5}
        ]
        """
        events = self.query_strain_history(
            strain_slug=strain_slug,
            dispensary=dispensary,
            store_id=store_id,
            limit=500,
        )
        if not events:
            return []

        # Group by store_id, then build periods
        by_store: dict[str, list] = defaultdict(list)
        for evt in events:
            sid = evt.get("store_id", "unknown")
            by_store[sid].append(evt)

        periods = []
        for sid, store_events in by_store.items():
            # Sort oldest to newest for period computation
            store_events.sort(key=lambda e: e.get("timestamp", ""))

            current_period = None
            for evt in store_events:
                event_type = evt.get("event")
                ts = evt.get("timestamp", "")

                if event_type in ("appeared", "restocked"):
                    if current_period and current_period.get("out_of_stock_at") is None:
                        # Already in an open period — update price/thc
                        current_period["price"] = evt.get("price") or current_period.get("price")
                        current_period["thc_percent"] = evt.get("thc_percent") or current_period.get("thc_percent")
                        continue
                    current_period = {
                        "store_id": sid,
                        "store_name": evt.get("store_name", ""),
                        "dispensary": evt.get("dispensary", ""),
                        "dispensary_name": evt.get("dispensary_name", ""),
                        "strain": evt.get("strain", ""),
                        "product_name": evt.get("product_name", ""),
                        "category": evt.get("category", ""),
                        "in_stock_from": ts,
                        "out_of_stock_at": None,
                        "days_available": None,
                        "price": evt.get("price"),
                        "thc_percent": evt.get("thc_percent"),
                    }
                    periods.append(current_period)

                elif event_type == "disappeared":
                    if current_period and current_period.get("out_of_stock_at") is None:
                        current_period["out_of_stock_at"] = ts
                        # Compute duration
                        try:
                            start = datetime.fromisoformat(
                                current_period["in_stock_from"].replace("Z", "+00:00")
                            )
                            end = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            current_period["days_available"] = round(
                                (end - start).total_seconds() / 86400, 1
                            )
                        except Exception:
                            pass
                    else:
                        # Disappeared without a matching appeared — orphan event
                        periods.append({
                            "store_id": sid,
                            "store_name": evt.get("store_name", ""),
                            "dispensary": evt.get("dispensary", ""),
                            "dispensary_name": evt.get("dispensary_name", ""),
                            "strain": evt.get("strain", ""),
                            "product_name": evt.get("product_name", ""),
                            "category": evt.get("category", ""),
                            "in_stock_from": None,
                            "out_of_stock_at": ts,
                            "days_available": None,
                            "price": evt.get("price"),
                            "thc_percent": evt.get("thc_percent"),
                        })

        # Sort newest first
        periods.sort(
            key=lambda p: p.get("in_stock_from") or p.get("out_of_stock_at") or "",
            reverse=True,
        )

        return periods

    def get_ledger_stats(self) -> dict:
        """Get aggregate statistics from the ledger."""
        container = self._get_container()
        if container is None:
            return {}

        try:
            # Total events
            total_query = "SELECT VALUE COUNT(1) FROM c"
            total = list(container.query_items(
                query=total_query,
                enable_cross_partition_query=True,
            ))
            total_events = total[0] if total else 0

            # Events by type
            type_query = (
                "SELECT c.event, COUNT(1) as count FROM c "
                "GROUP BY c.event"
            )
            by_type = list(container.query_items(
                query=type_query,
                enable_cross_partition_query=True,
            ))

            # Unique strains tracked
            strain_query = (
                "SELECT VALUE COUNT(1) FROM "
                "(SELECT DISTINCT c.strain_slug FROM c)"
            )
            strain_count = list(container.query_items(
                query=strain_query,
                enable_cross_partition_query=True,
            ))

            return {
                "total_events": total_events,
                "by_event_type": {r["event"]: r["count"] for r in by_type},
                "unique_strains_tracked": strain_count[0] if strain_count else 0,
            }
        except Exception as e:
            logger.error(f"Ledger stats query failed: {e}")
            return {"error": str(e)}


# =============================================================================
# Helpers
# =============================================================================

def _safe_float(val) -> float | None:
    """Safely convert a value to float."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# =============================================================================
# Backwards Compatibility Aliases
# =============================================================================

# Keep the old class name working for imports in stock_routes.py and main.py
StockIndexer = StockIndexerV2
StockItem = StockItemV2
IndexMetadata = None  # No longer a dataclass, metadata is a plain dict


def main():
    """CLI entry point: build and save the stock index."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    indexer = StockIndexerV2()
    index = indexer.build_index()
    indexer.save_index(index)

    meta = index["metadata"]
    print(f"\n=== Stock Index v2 Built ===")
    print(f"Total items: {meta['total_items']}")
    print(f"Unique strains: {meta['unique_strains']}")
    print(f"Dispensaries: {list(meta['dispensaries'].keys())}")
    print(f"Enrichment: COA={meta['enrichment']['with_coa']}, "
          f"Terpenes={meta['enrichment']['with_terpenes']}, "
          f"Genetics={meta['enrichment']['with_genetics']}, "
          f"Location={meta['enrichment']['with_location']}")
    print(f"Build date: {meta['build_date']}")


if __name__ == "__main__":
    main()
