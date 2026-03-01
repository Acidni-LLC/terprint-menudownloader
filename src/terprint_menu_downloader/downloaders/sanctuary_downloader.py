"""
Sanctuary Medicinals - Menu Downloader
=======================================
Platform  : Sweed POS  (sanctuarymed.com/shop/florida)
Coverage  : 25 Florida dispensary stores
grower_id : 9

Follows the same interface contract as other downloaders
(GreenDragonDownloader, CuraleafDownloader).

Usage (standalone):
    from terprint_menu_downloader.downloaders.sanctuary_downloader import SanctuaryDownloader
    dl = SanctuaryDownloader()
    results = dl.download()      # [(path_or_key, data_dict), ...]
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Package vs. standalone detection
# -------------------------------------------------------------------
_RUNNING_AS_PACKAGE = "terprint_menu_downloader" in __name__

DEFAULT_STORES_PER_BATCH = 5
DEFAULT_PARALLEL_STORES  = 2


class SanctuaryDownloader:
    """Download menu data from Sanctuary Medicinals Florida dispensaries."""

    def __init__(
        self,
        output_dir: str = None,
        azure_manager=None,
        max_products_per_store: Optional[int] = None,
        store_batch: Optional[int] = None,
        stores_per_batch: int = DEFAULT_STORES_PER_BATCH,
        parallel_stores: int = DEFAULT_PARALLEL_STORES,
    ):
        self.output_dir            = output_dir
        self.azure_manager         = azure_manager
        self.max_products_per_store = max_products_per_store
        self.dispensary_name       = "Sanctuary Medicinals"

        self.store_batch           = store_batch
        self.stores_per_batch      = stores_per_batch
        self.parallel_stores       = parallel_stores

        # Import config & scraper (handles both package and standalone usage)
        if _RUNNING_AS_PACKAGE:
            from ..dispensaries.sanctuary import SANCTUARY_CONFIG, FL_STORES
            from ..dispensaries.sanctuary.scraper import SanctuaryStoreScraper
        else:
            from terprint_menu_downloader.dispensaries.sanctuary import SANCTUARY_CONFIG, FL_STORES
            from terprint_menu_downloader.dispensaries.sanctuary.scraper import SanctuaryStoreScraper

        self.config         = SANCTUARY_CONFIG
        self.all_stores     = FL_STORES
        self.scraper_class  = SanctuaryStoreScraper

        # Determine which stores to download for this batch
        self.stores = self._get_batch_stores()

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def _get_batch_stores(self) -> List:
        if self.store_batch is None:
            return self.all_stores
        start = self.store_batch * self.stores_per_batch
        end   = start + self.stores_per_batch
        batch = self.all_stores[start:end]
        logger.info(
            f"Sanctuary batch {self.store_batch}: "
            f"stores {start}-{end-1} ({len(batch)} stores)"
        )
        return batch

    @property
    def total_batches(self) -> int:
        return (len(self.all_stores) + self.stores_per_batch - 1) // self.stores_per_batch

    @property
    def store_count(self) -> int:
        return len(self.stores)

    @property
    def total_store_count(self) -> int:
        return len(self.all_stores)

    # ------------------------------------------------------------------
    # Core download logic
    # ------------------------------------------------------------------

    def download_location(self, store_slug: str, store_name: str = None) -> Optional[Dict]:
        """
        Download menu data for a single store.

        Returns a dict with the standard dispensary data envelope,
        or None on failure.
        """
        store = next((s for s in self.all_stores if s.slug == store_slug), None)
        if not store:
            logger.warning(f"Sanctuary: store '{store_slug}' not found in config")
            return None

        display_name = store_name or store.name

        try:
            scraper = self.scraper_class(config=self.config)
            result  = scraper.scrape_store(
                store,
                include_details=True,
                max_products=self.max_products_per_store,
            )
            products = result.get("products", [])

            return {
                "dispensary":       "sanctuary",
                "dispensary_name":  "Sanctuary Medicinals",
                "store_slug":       store_slug,
                "store_name":       display_name,
                "store_id":         store_slug,
                "city":             store.city,
                "state":            "FL",
                "timestamp":        datetime.now(timezone.utc).isoformat(),
                "download_time":    datetime.now(timezone.utc).isoformat(),
                "product_count":    len(products),
                "products":         products,
                "metadata": {
                    "platform":           "Sweed POS",
                    "platform_type":      "html_scrape",
                    "grower_id":          9,
                    "downloader_version": "1.0",
                    "batch":              self.store_batch,
                    "stores_per_batch":   self.stores_per_batch,
                },
            }
        except Exception as e:
            logger.error(f"Sanctuary: error downloading {store_slug}: {e}", exc_info=True)
            return None

    def _download_store_with_save(self, store) -> Optional[Tuple[str, Dict]]:
        """Download one store and persist to Azure Data Lake (or local/memory)."""
        store_slug  = store.slug
        store_name  = store.name

        try:
            data = self.download_location(store_slug, store_name)

            if not data or data.get("product_count", 0) == 0:
                logger.warning(f"Sanctuary: no products for {store_name}")
                return None

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename  = f"sanctuary_products_store_{store_slug}_{timestamp}.json"
            data["raw_response_size"] = len(json.dumps(data))

            # --- Azure Data Lake ---
            if self.azure_manager:
                date_folder = datetime.now().strftime("%Y/%m/%d")
                azure_path  = f"dispensaries/sanctuary/{date_folder}/{filename}"
                success = self.azure_manager.save_json_to_data_lake(
                    json_data=data,
                    file_path=azure_path,
                    overwrite=True,
                )
                if success:
                    logger.info(
                        f"Sanctuary ✓ {store_name}: "
                        f"{data['product_count']} products → azure://{azure_path}"
                    )
                    return (f"azure://{azure_path}", data)
                else:
                    logger.error(f"Sanctuary: Azure upload failed for {store_name}")
                    return None

            # --- Local file ---
            elif self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Sanctuary ✓ {store_name}: {data['product_count']} products → {filepath}")
                return (filepath, data)

            # --- In-memory only ---
            else:
                logger.info(f"Sanctuary ✓ {store_name}: {data['product_count']} products (in-memory)")
                return (f"memory://{store_slug}", data)

        except Exception as e:
            logger.error(f"Sanctuary: error processing {store_name}: {e}", exc_info=True)
            return None

    def download_single_store(self, store_slug: str) -> Optional[Tuple[str, Dict]]:
        """Download a single store by slug."""
        store = next((s for s in self.all_stores if s.slug == store_slug), None)
        if not store:
            logger.error(f"Sanctuary: store '{store_slug}' not found")
            return None
        return self._download_store_with_save(store)

    def download(self, parallel: bool = True) -> List[Tuple[str, Dict]]:
        """
        Download menu data for all stores in this batch.

        Args:
            parallel: Download stores concurrently (default: True)

        Returns:
            List of (path_or_key, data_dict) tuples for successful stores.
        """
        results: List[Tuple[str, Dict]] = []

        if not self.stores:
            logger.warning("Sanctuary: no stores configured for this batch")
            return results

        logger.info(
            f"Sanctuary: downloading {len(self.stores)} stores "
            f"(parallel={parallel}, workers={self.parallel_stores})"
        )

        if parallel:
            with ThreadPoolExecutor(max_workers=self.parallel_stores) as executor:
                futures = {
                    executor.submit(self._download_store_with_save, store): store.slug
                    for store in self.stores
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        logger.error(f"Sanctuary: parallel download error: {e}")
        else:
            for store in self.stores:
                result = self._download_store_with_save(store)
                if result:
                    results.append(result)

        logger.info(f"Sanctuary: ✓ {len(results)}/{len(self.stores)} stores downloaded")
        return results

    def download_all_batches(self) -> Dict[int, List[Tuple[str, Dict]]]:
        """Download all stores across all batches."""
        all_results: Dict[int, List] = {}
        for batch_idx in range(self.total_batches):
            logger.info(f"Sanctuary: batch {batch_idx + 1}/{self.total_batches}")
            dl = SanctuaryDownloader(
                output_dir=self.output_dir,
                azure_manager=self.azure_manager,
                max_products_per_store=self.max_products_per_store,
                store_batch=batch_idx,
                stores_per_batch=self.stores_per_batch,
                parallel_stores=self.parallel_stores,
            )
            all_results[batch_idx] = dl.download(parallel=True)
        return all_results

    def __repr__(self) -> str:
        return (
            f"SanctuaryDownloader("
            f"stores={self.store_count}/{self.total_store_count}, "
            f"batch={self.store_batch}, "
            f"parallel={self.parallel_stores})"
        )
