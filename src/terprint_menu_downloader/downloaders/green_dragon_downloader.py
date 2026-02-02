"""
Green Dragon Cannabis Company - Menu Downloader
Wrapper around Green Dragon config and scraper packages

Platform: Squarespace (HTML Scraping)
Coverage: 13 FL dispensary stores
"""
import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Detect if running as package
_RUNNING_AS_PACKAGE = "terprint_menu_downloader" in __name__

# Default configuration
DEFAULT_STORES_PER_BATCH = 5  # 5 stores per batch
DEFAULT_PARALLEL_STORES = 2   # 2 concurrent downloads


class GreenDragonDownloader:
    """Download menu data from Green Dragon Florida dispensaries"""

    def __init__(
        self,
        output_dir: str = None,
        azure_manager=None,
        max_products_per_store: int = None,
        store_batch: int = None,
        stores_per_batch: int = DEFAULT_STORES_PER_BATCH,
        parallel_stores: int = DEFAULT_PARALLEL_STORES
    ):
        self.output_dir = output_dir
        self.azure_manager = azure_manager
        self.max_products_per_store = max_products_per_store
        self.dispensary_name = 'Green Dragon'

        # Batching configuration
        self.store_batch = store_batch
        self.stores_per_batch = stores_per_batch
        self.parallel_stores = parallel_stores

        # Import config package from dispensaries folder
        if _RUNNING_AS_PACKAGE:
            from ..dispensaries.green_dragon import GREEN_DRAGON_CONFIG, FL_STORES
            from ..dispensaries.green_dragon.scraper import GreenDragonScraper
        else:
            from terprint_menu_downloader.dispensaries.green_dragon import GREEN_DRAGON_CONFIG, FL_STORES
            from terprint_menu_downloader.dispensaries.green_dragon.scraper import GreenDragonScraper

        self.config = GREEN_DRAGON_CONFIG
        self.all_stores = FL_STORES
        self.scraper_class = GreenDragonScraper

        # Calculate which stores to download based on batch
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
    def total_batches(self) -> int:
        """Return the total number of batches needed."""
        return (len(self.all_stores) + self.stores_per_batch - 1) // self.stores_per_batch

    @property
    def store_count(self) -> int:
        """Return the number of stores configured for this batch."""
        return len(self.stores)

    @property
    def total_store_count(self) -> int:
        """Return the total number of stores across all batches."""
        return len(self.all_stores)

    def download_location(self, store_slug: str, store_name: str = None) -> Optional[Dict]:
        """
        Download menu data for a specific store.

        Args:
            store_slug: Store slug (e.g., "boynton-beach")
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

            # Use synchronous wrapper for the async scraper
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                import asyncio
                
                # Synchronous wrapper
                async def _scrape():
                    async with self.scraper_class() as scraper:
                        return await scraper.scrape_location(store_info)
                
                result = loop.run_until_complete(_scrape())
                products = result.get("products", [])

            finally:
                loop.close()

            return {
                "dispensary": "green_dragon",
                "store_slug": store_slug,
                "store_name": display_name,
                "store_id": store_slug,
                "state": "FL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "download_time": datetime.now(timezone.utc).isoformat(),
                "product_count": len(products),
                "products": products,
                "metadata": {
                    "platform": "Squarespace",
                    "platform_type": "html_scrape",
                    "coa_portal": "https://coaportal.com/greendragon",
                    "downloader_version": "1.0",
                    "batch": self.store_batch,
                    "stores_per_batch": self.stores_per_batch,
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
            if not data:
                return None

            # Save to Azure blob storage if manager provided
            if self.azure_manager and self.output_dir:
                blob_name = f"dispensaries/green-dragon/{store_slug}_menu.json"
                try:
                    self.azure_manager.upload_json_to_blob(
                        json.dumps(data, indent=2),
                        blob_name
                    )
                    logger.info(f"✓ Uploaded {blob_name}")
                except Exception as e:
                    logger.error(f"Failed to upload {blob_name}: {e}")

            # Save locally if output_dir specified
            if self.output_dir:
                os.makedirs(self.output_dir, exist_ok=True)
                local_path = os.path.join(self.output_dir, f"{store_slug}_menu.json")
                with open(local_path, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info(f"✓ Saved locally to {local_path}")

            return (store_slug, data)
        except Exception as e:
            logger.error(f"Error downloading/saving {store_slug}: {e}")
            return None

    def download_single_store(self, store_slug: str) -> Optional[Tuple[str, Dict]]:
        """Download a single store by slug"""
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
            List of (store_slug, data) tuples
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

        logger.info(f"✓ Downloaded {len(results)}/{len(self.stores)} stores")
        return results

    def download_all_batches(self, parallel_stores: int = None) -> Dict[int, List[Tuple[str, Dict]]]:
        """
        Download all stores across all batches.

        Args:
            parallel_stores: Override parallel_stores setting

        Returns:
            Dict mapping batch_index -> list of (store_slug, data) tuples
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
