"""
Green Dragon menu downloader.

Downloads product menus from Green Dragon dispensaries using the Sweed POS
platform at shop.greendragon.com. Supports batch processing, Azure Data Lake
upload, and parallel store downloads.

Version: 2.0 - Sweed POS integration (replaces Squarespace scraper)
"""

import json
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Constants
DEFAULT_STORES_PER_BATCH = 6
DEFAULT_PARALLEL_STORES = 3

# Detect if running as part of the installed package
try:
    from ..dispensaries.green_dragon import FL_CATEGORIES
    _RUNNING_AS_PACKAGE = True
except ImportError:
    _RUNNING_AS_PACKAGE = False


class GreenDragonDownloader:
    """
    Download Green Dragon menus from Sweed POS (shop.greendragon.com).

    Supports:
    - Single store or batch download
    - Azure Data Lake or local file output
    - COA (Certificate of Analysis) PDF download from LabDrive
    - Parallel store downloads via ThreadPoolExecutor
    """

    def __init__(
        self,
        output_dir: str = None,
        azure_manager=None,
        max_products_per_store: Optional[int] = None,
        store_batch: Optional[int] = None,
        stores_per_batch: int = DEFAULT_STORES_PER_BATCH,
        parallel_stores: int = DEFAULT_PARALLEL_STORES,
        include_coa: bool = False,
    ):
        self.output_dir             = output_dir
        self.azure_manager          = azure_manager
        self.max_products_per_store = max_products_per_store
        self.dispensary_name        = "Green Dragon"
        self.include_coa            = include_coa

        self.store_batch            = store_batch
        self.stores_per_batch       = stores_per_batch
        self.parallel_stores        = parallel_stores

        # Import config & scraper (handles both package and standalone usage)
        if _RUNNING_AS_PACKAGE:
            from ..dispensaries.green_dragon import GREEN_DRAGON_CONFIG, FL_STORES
            from ..dispensaries.green_dragon.scraper import GreenDragonStoreScraper
        else:
            from terprint_menu_downloader.dispensaries.green_dragon import GREEN_DRAGON_CONFIG, FL_STORES
            from terprint_menu_downloader.dispensaries.green_dragon.scraper import GreenDragonStoreScraper

        self.config         = GREEN_DRAGON_CONFIG
        self.all_stores     = FL_STORES
        self.scraper_class  = GreenDragonStoreScraper

        # Determine which stores to download for this batch
        self.stores = self._get_batch_stores()

    def _get_batch_stores(self) -> List:
        """Get stores for the current batch, or all stores if no batch specified."""
        if self.store_batch is None:
            return self.all_stores

        start_idx = self.store_batch * self.stores_per_batch
        end_idx = start_idx + self.stores_per_batch
        batch_stores = self.all_stores[start_idx:end_idx]

        logger.info(f"Green Dragon batch {self.store_batch}: stores {start_idx}-{end_idx-1} ({len(batch_stores)} stores)")
        return batch_stores

    @property
    def store_count(self) -> int:
        """Return the number of stores configured for this batch."""
        return len(self.stores)

    @property
    def total_batches(self) -> int:
        """Return the total number of batches needed."""
        return (len(self.all_stores) + self.stores_per_batch - 1) // self.stores_per_batch

    @property
    def total_store_count(self) -> int:
        """Return the total number of stores across all batches."""
        return len(self.all_stores)

    def download_location(self, store_slug: str, store_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Download menu data for a specific store.

        Args:
            store_slug: Store slug (e.g., "boynton-beach-east")
            store_name: Optional display name for the store

        Returns:
            Dict with store data or None if failed
        """
        try:
            # Get store info from config
            store_info = next((s for s in self.all_stores if s.slug == store_slug), None)
            if not store_info:
                logger.warning(f"Store {store_slug} not found in config")
                return None

            display_name = store_name or store_info.name

            # Use the sync Sweed POS scraper
            scraper = self.scraper_class()
            result = scraper.scrape_store(
                store=store_info,
                categories=FL_CATEGORIES,
                include_coa=self.include_coa,
                coa_output_dir=self.output_dir,
                max_products=self.max_products_per_store,
            )
            products = result.get("products", [])

            return {
                "dispensary": "green_dragon",
                "dispensary_name": self.dispensary_name,
                "store_slug": store_slug,
                "store_name": display_name,
                "store_id": store_slug,
                "state": store_info.state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "download_time": datetime.now(timezone.utc).isoformat(),
                "product_count": len(products),
                "products": products,
                "metadata": {
                    "platform": "Sweed POS",
                    "platform_type": "json_extraction",
                    "coa_source": "LabDrive (mete.labdrive.net)",
                    "downloader_version": "2.0",
                    "batch": self.store_batch,
                    "stores_per_batch": self.stores_per_batch,
                    "include_coa": self.include_coa,
                }
            }
        except Exception as e:
            logger.error(f"Error downloading {store_slug}: {e}")
            return None

    def _download_store_with_save(self, store) -> Optional[Tuple[str, Dict]]:
        """Download a single store and save to Azure/local. Thread-safe for parallel execution."""
        store_slug = store.slug
        store_name = store.name

        try:
            data = self.download_location(store_slug, store_name)

            if data and data.get('product_count', 0) > 0:
                # Create filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"green_dragon_products_store_{store_slug}_{timestamp}.json"

                # Add raw response size for tracking
                data['raw_response_size'] = len(json.dumps(data))

                # Save to Azure Data Lake if available
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        azure_path = f"dispensaries/green_dragon/{date_folder}/{filename}"

                        success = self.azure_manager.save_json_to_data_lake(
                            json_data=data,
                            file_path=azure_path,
                            overwrite=True
                        )

                        if success:
                            logger.info(f"Uploaded {store_name}: {data['product_count']} products")
                            return (f"azure://{azure_path}", data)
                        else:
                            logger.error(f"Failed {store_name}: Azure upload failed")
                            return None
                    except Exception as e:
                        logger.error(f"Failed {store_name}: Azure error: {e}")
                        return None
                else:
                    # No Azure manager - save locally if output_dir specified
                    if self.output_dir:
                        os.makedirs(self.output_dir, exist_ok=True)
                        filepath = os.path.join(self.output_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2)
                        logger.info(f"Saved {store_name}: {data['product_count']} products (local)")
                        return (filepath, data)
                    else:
                        # In-memory only
                        logger.info(f"Downloaded {store_name}: {data['product_count']} products (in-memory)")
                        return (f"memory://{store_slug}", data)
            else:
                logger.warning(f"No products found for {store_name}")
                return None

        except Exception as e:
            logger.error(f"Error downloading {store_name}: {e}")
            return None

    def download_single_store(self, store_slug: str) -> Optional[Tuple[str, Dict]]:
        """Download a single store by slug."""
        store = next((s for s in self.all_stores if s.slug == store_slug), None)
        if not store:
            logger.error(f"Store {store_slug} not found")
            return None
        return self._download_store_with_save(store)

    def download(self, parallel: bool = True) -> List[Tuple[str, Dict]]:
        """
        Download menu data for all stores in this batch.

        Args:
            parallel: If True, download stores in parallel; if False, sequential

        Returns:
            List of (filepath, data) tuples
        """
        results = []

        if not self.stores:
            logger.warning("No stores configured for this batch")
            return results

        logger.info(f"Downloading {len(self.stores)} stores from {self.dispensary_name}")

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
                        logger.error(f"Error in parallel download: {e}")
        else:
            # Sequential download
            for store in self.stores:
                result = self._download_store_with_save(store)
                if result:
                    results.append(result)

        logger.info(f"Downloaded {len(results)}/{len(self.stores)} stores")
        return results

    def download_all_batches(self, parallel_stores: int = None) -> Dict[int, List[Tuple[str, Dict]]]:
        """
        Download all stores across all batches.

        Args:
            parallel_stores: Override parallel_stores setting

        Returns:
            Dict mapping batch_index -> list of (filepath, data) tuples
        """
        parallel_stores = parallel_stores or self.parallel_stores
        all_results = {}

        for batch_idx in range(self.total_batches):
            logger.info(f"Processing batch {batch_idx + 1}/{self.total_batches}")
            downloader = GreenDragonDownloader(
                output_dir=self.output_dir,
                azure_manager=self.azure_manager,
                max_products_per_store=self.max_products_per_store,
                store_batch=batch_idx,
                stores_per_batch=self.stores_per_batch,
                parallel_stores=parallel_stores,
                include_coa=self.include_coa,
            )
            batch_results = downloader.download(parallel=True)
            all_results[batch_idx] = batch_results

        return all_results

    def __repr__(self) -> str:
        return (
            f"GreenDragonDownloader("
            f"stores={self.store_count}/{self.total_store_count}, "
            f"batch={self.store_batch}, "
            f"parallel={self.parallel_stores})"
        )