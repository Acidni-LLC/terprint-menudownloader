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
    last_seen: str = ""
    freshness_hours: float | None = None
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
}

# All dispensaries we track
EXPECTED_DISPENSARIES = list(DISPENSARY_NAMES.keys())


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
        for prefix in (
            f"{dispensary}-products-store-{dispensary}-",
            f"{dispensary}-products-store-",
            f"{dispensary}-menu-{dispensary}-",
            f"{dispensary}-menu-",
            f"{dispensary}-store-",
            f"{dispensary}-",
        ):
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break
        # Remove timestamp suffix (YYYYMMDD-HHMMSS or YYYYMMDD)
        clean = re.sub(r"-?\d{8}(-\d{6})?$", "", clean).strip("-")

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
        """Find the most recent menu blobs for a dispensary."""
        container = self._get_blob_container()
        if not container:
            return []

        for days_back in range(max_days_back):
            check_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            date_str = check_date.strftime("%Y/%m/%d")
            prefix = f"dispensaries/{dispensary}/{date_str}/"

            blobs = list(container.list_blobs(name_starts_with=prefix))
            if blobs:
                blobs.sort(key=lambda b: b.name, reverse=True)
                logger.info(f"Found {len(blobs)} menu blobs for {dispensary} ({days_back}d ago)")
                return blobs

        logger.warning(f"No menu files for {dispensary} in last {max_days_back} days")
        return []

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

                strain = self._extract_field(product, [
                    "strain", "strainName", "strain_name", "name", "productName", "title"
                ]) or "Unknown"

                batch_id = self._extract_field(product, [
                    "batch_number", "batchNumber", "batchId", "batch_id", "sku", "id"
                ]) or "unknown"

                category = self._extract_field(product, [
                    "category", "productCategory", "product_category", "type"
                ]) or "unknown"

                product_name = self._extract_field(product, [
                    "name", "productName", "product_name", "title"
                ]) or strain

                strain_slug = self.normalize_strain_name(strain)
                item_id = hashlib.md5(
                    f"{dispensary}:{store.store_id}:{strain_slug}:{batch_id}".encode()
                ).hexdigest()[:12]

                # Extract basic cannabinoid/price data from menu
                thc = _safe_float(product.get("thc") or product.get("thcPercent") or product.get("thc_percent"))
                cbd = _safe_float(product.get("cbd") or product.get("cbdPercent") or product.get("cbd_percent"))
                price = _safe_float(product.get("price"))
                weight = _safe_float(product.get("weight") or product.get("weightGrams") or product.get("weight_grams"))

                # Extract terpene profile from menu if available
                terpene_profile = {}
                menu_terpenes = product.get("terpenes")
                if isinstance(menu_terpenes, dict):
                    terpene_profile = {k: _safe_float(v) for k, v in menu_terpenes.items() if _safe_float(v) is not None}

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

                items.append(item)

            logger.info(f"Extracted {len(items)} items from {blob_name}")
            return items

        except Exception as e:
            logger.error(f"Error processing menu file {blob_name}: {e}")
            return []

    @staticmethod
    def _extract_products(data: Any) -> list:
        """Extract product array from various menu JSON formats."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("products", "data", "items", "menu", "results"):
                val = data.get(key)
                if isinstance(val, list):
                    return val
                if isinstance(val, dict):
                    for sub_key in ("products", "items", "results"):
                        sub = val.get(sub_key)
                        if isinstance(sub, list):
                            return sub
        return []

    @staticmethod
    def _extract_field(product: dict, field_names: list[str]) -> str | None:
        """Extract a field trying multiple possible key names."""
        for name in field_names:
            val = product.get(name)
            if val:
                return str(val).strip()
        return None

    @staticmethod
    def _normalize_category(category: str) -> str:
        """Normalize product category to standard values."""
        cat = category.lower().strip()
        mapping = {
            "flower": "Flower", "flowers": "Flower", "bud": "Flower",
            "pre-roll": "Pre-Rolls", "pre-rolls": "Pre-Rolls", "preroll": "Pre-Rolls",
            "prerolls": "Pre-Rolls", "pre roll": "Pre-Rolls", "pre rolls": "Pre-Rolls",
            "joint": "Pre-Rolls", "joints": "Pre-Rolls",
            "vape": "Vape", "vapes": "Vape", "cartridge": "Vape", "cartridges": "Vape",
            "cart": "Vape", "carts": "Vape", "pod": "Vape", "pods": "Vape",
            "concentrate": "Concentrates", "concentrates": "Concentrates",
            "extract": "Concentrates", "extracts": "Concentrates",
            "wax": "Concentrates", "shatter": "Concentrates", "rosin": "Concentrates",
            "live resin": "Concentrates", "live rosin": "Concentrates",
            "edible": "Edibles", "edibles": "Edibles",
            "gummy": "Edibles", "gummies": "Edibles",
            "topical": "Topicals", "topicals": "Topicals",
            "cream": "Topicals", "lotion": "Topicals",
            "tincture": "Tinctures", "tinctures": "Tinctures",
            "oral": "Tinctures", "sublingual": "Tinctures",
            "capsule": "Capsules", "capsules": "Capsules",
            "rso": "RSO", "rick simpson": "RSO",
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
