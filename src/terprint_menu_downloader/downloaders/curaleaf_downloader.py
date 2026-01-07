"""
Curaleaf Florida Downloader Module
Wrapper around the config package from Menu Explorer.

Platform: SweedPOS (HTML Scraping)
Coverage: 65 FL dispensary stores
Terpene Data: ~85% of products have terpene profiles

Supports batching for Azure Functions timeout constraints:
- store_batch: Which batch of stores to download (0-based index)
- stores_per_batch: Number of stores per batch (default 15)
- parallel_stores: Number of stores to download in parallel (default 3)
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

# Default batching configuration
DEFAULT_STORES_PER_BATCH = 15  # ~3-4 min per batch with parallel downloads
DEFAULT_PARALLEL_STORES = 3   # Download 3 stores simultaneously


class CuraleafDownloader:
    """Download menu data from Curaleaf Florida dispensaries.
    
    Supports batching and parallel downloads to work within Azure Functions timeout limits.
    """

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
        self.dispensary_name = 'Curaleaf'
        
        # Batching configuration
        self.store_batch = store_batch  # None = all stores, 0/1/2/3 = specific batch
        self.stores_per_batch = stores_per_batch
        self.parallel_stores = parallel_stores
        
        # Import config package from dispensaries folder
        if _RUNNING_AS_PACKAGE:
            from ..dispensaries.curaleaf import CURALEAF_CONFIG, FL_STORES
            from ..dispensaries.curaleaf.scraper import CuraleafScraper
        else:
            from terprint_menu_downloader.dispensaries.curaleaf import CURALEAF_CONFIG, FL_STORES
            from terprint_menu_downloader.dispensaries.curaleaf.scraper import CuraleafScraper
        
        self.config = CURALEAF_CONFIG
        self.all_stores = FL_STORES
        self.scraper_class = CuraleafScraper
        
        # Calculate which stores to download based on batch
        self.stores = self._get_batch_stores()
    
    def _get_batch_stores(self) -> List[Dict]:
        """Get stores for the current batch, or all stores if no batch specified."""
        if self.store_batch is None:
            return self.all_stores
        
        start_idx = self.store_batch * self.stores_per_batch
        end_idx = start_idx + self.stores_per_batch
        batch_stores = self.all_stores[start_idx:end_idx]
        
        logger.info(f"Curaleaf batch {self.store_batch}: stores {start_idx}-{end_idx-1} ({len(batch_stores)} stores)")
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
            store_slug: Store slug (e.g., "curaleaf-dispensary-tampa")
            store_name: Optional display name for the store
            
        Returns:
            Dict with store data or None if failed
        """
        try:
            # Get store info from config - check all_stores since stores may be filtered
            store_info = next((s for s in self.all_stores if s['slug'] == store_slug), {})
            display_name = store_name or store_info.get('name', store_slug)
            
            # Use the scraper from config package
            with self.scraper_class() as scraper:
                products = scraper.scrape_store_menu_with_terpenes(
                    store_slug,
                    max_products=self.max_products_per_store,
                    sample_terpenes=None  # Get all terpenes
                )

            return {
                "dispensary": "curaleaf",
                "store_slug": store_slug,
                "store_name": display_name,
                "store_id": store_info.get('unique_id', store_slug),
                "state": "FL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "download_time": datetime.now(timezone.utc).isoformat(),
                "product_count": len(products),
                "products": products,
                "metadata": {
                    "platform": self.config.platform,
                    "platform_type": self.config.platform_type,
                    "terpene_source": self.config.terpene_source,
                    "downloader_version": "1.1",  # Updated for batching support
                    "batch": self.store_batch,
                    "stores_per_batch": self.stores_per_batch,
                }
            }
        except Exception as e:
            logger.error(f"Error downloading {store_slug}: {e}")
            return None

    def _download_store_with_save(self, store: Dict) -> Optional[Tuple[str, Dict]]:
        """Download a single store and save to Azure/local. Thread-safe for parallel execution."""
        store_slug = store['slug']
        store_name = store['name']
        
        try:
            result = self.download_location(store_slug, store_name)
            
            if result and result.get('product_count', 0) > 0:
                # Create filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"curaleaf_products_store_{store_slug}_{timestamp}.json"
                
                # Add raw response size for tracking
                result['raw_response_size'] = len(json.dumps(result))
                
                # Save to Azure Data Lake if available
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        azure_path = f"dispensaries/curaleaf/{date_folder}/{filename}"
                        
                        success = self.azure_manager.save_json_to_data_lake(
                            json_data=result,
                            file_path=azure_path,
                            overwrite=True
                        )
                        
                        if success:
                            logger.info(f"✓ {store_name}: {result['product_count']} products")
                            return (f"azure://{azure_path}", result)
                        else:
                            logger.error(f"✗ {store_name}: Azure upload failed")
                            return None
                    except Exception as e:
                        logger.error(f"✗ {store_name}: Azure error: {e}")
                        return None
                else:
                    # No Azure manager - save locally if output_dir specified
                    if self.output_dir:
                        os.makedirs(self.output_dir, exist_ok=True)
                        filepath = os.path.join(self.output_dir, filename)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2)
                        logger.info(f"✓ {store_name}: {result['product_count']} products (local)")
                        return (filepath, result)
                    else:
                        # In-memory only
                        logger.info(f"✓ {store_name}: {result['product_count']} products (in-memory)")
                        return (f"memory://{store_slug}", result)
            else:
                logger.warning(f"✗ {store_name}: No products found")
                return None
                
        except Exception as e:
            logger.error(f"✗ {store_name}: Error: {e}")
            return None

    def download(self, parallel: bool = True) -> List[Tuple[str, Dict]]:
        """
        Download from stores in current batch (or all stores if no batch specified).
        Main entry point for orchestrator compatibility.
        
        Args:
            parallel: If True, download multiple stores in parallel (default True)
        
        Returns:
            List of (filepath, data) tuples
        """
        batch_info = f" (batch {self.store_batch}/{self.total_batches-1})" if self.store_batch is not None else ""
        logger.info(f"\n{'='*60}")
        logger.info(f"{self.dispensary_name} - Downloading {len(self.stores)} stores{batch_info}")
        if parallel:
            logger.info(f"Parallel mode: {self.parallel_stores} concurrent downloads")
        logger.info(f"{'='*60}\n")

        results = []
        success_count = 0
        fail_count = 0
        
        if parallel and self.parallel_stores > 1:
            # Parallel download using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.parallel_stores) as executor:
                future_to_store = {
                    executor.submit(self._download_store_with_save, store): store 
                    for store in self.stores
                }
                
                for future in as_completed(future_to_store):
                    store = future_to_store[future]
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        logger.error(f"✗ {store['name']}: Thread error: {e}")
                        fail_count += 1
        else:
            # Sequential download (original behavior)
            for store in self.stores:
                result = self._download_store_with_save(store)
                if result:
                    results.append(result)
                    success_count += 1
                else:
                    fail_count += 1
        
        logger.info(f"\n{self.dispensary_name} Download Complete{batch_info}:")
        logger.info(f"   Success: {success_count}/{len(self.stores)} stores")
        logger.info(f"   Failed: {fail_count}/{len(self.stores)} stores")
        logger.info(f"   Total products: {sum(r[1].get('product_count', 0) for r in results)}")
        
        return results

    def download_single_store(self, store_slug: str) -> Optional[Tuple[str, Dict]]:
        """
        Download from a single store (for testing).
        
        Args:
            store_slug: Store slug to download
            
        Returns:
            (filepath, data) tuple or None if failed
        """
        # Search in all_stores, not just the batched stores
        store_info = next((s for s in self.all_stores if s['slug'] == store_slug), None)
        if not store_info:
            logger.error(f"Store not found: {store_slug}")
            return None
        
        result = self.download_location(store_slug, store_info['name'])
        if result:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"curaleaf_products_store_{store_slug}_{timestamp}.json"
            
            if self.azure_manager:
                date_folder = datetime.now().strftime("%Y/%m/%d")
                azure_path = f"dispensaries/curaleaf/{date_folder}/{filename}"
                success = self.azure_manager.save_json_to_data_lake(
                    json_data=result,
                    file_path=azure_path,
                    overwrite=True
                )
                if success:
                    return (f"azure://{azure_path}", result)
            
            return (f"memory://{store_slug}", result)
        
        return None
