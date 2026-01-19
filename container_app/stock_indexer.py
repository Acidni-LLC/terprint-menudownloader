"""
Stock Index Builder

Builds searchable stock index from consolidated batch files.
Updated after each batch processing run to show current inventory.

Storage:
- stock-index/current.json - Latest full index
- stock-index/by-strain/{strain_normalized}.json - Per-strain lookups
- stock-index/by-dispensary/{dispensary}.json - Per-dispensary inventory
- stock-index/metadata.json - Index build metadata

Copyright (c) 2026 Acidni LLC
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


@dataclass
class StockItem:
    """A product in stock."""
    batch_id: str
    strain: str
    strain_normalized: str
    dispensary: str
    category: str
    product_name: str
    
    # Cannabis data
    thc_percent: Optional[float] = None
    cbd_percent: Optional[float] = None
    terpenes: Optional[Dict[str, float]] = None
    
    # Pricing/availability
    price: Optional[float] = None
    weight_grams: Optional[float] = None
    in_stock: bool = True
    
    # Location data (for proximity search)
    store_location: Optional[str] = None  # e.g., "miami", "tampa"
    store_name: Optional[str] = None      # e.g., "Cookies Miami"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    
    # Metadata
    last_seen: str = None
    source_file: str = None


@dataclass
class IndexMetadata:
    """Metadata about the stock index."""
    build_date: str
    total_items: int
    dispensaries: List[str]
    unique_strains: int
    batch_files_processed: int
    source_date_range: Dict[str, str]


class StockIndexer:
    """
    Builds searchable stock index from batch files.
    
    Usage:
        indexer = StockIndexer()
        
        # Build from today's batches
        index = indexer.build_index_from_date('20260115')
        indexer.save_index(index)
        
        # Or build from latest consolidated file
        index = indexer.build_index_from_latest()
        indexer.save_index(index)
    """
    
    STORAGE_ACCOUNT = "stterprintsharedgen2"
    CONTAINER_NAME = "jsonfiles"
    INDEX_PREFIX = "stock-index"
    
    def __init__(self):
        credential = DefaultAzureCredential()
        self.blob_service = BlobServiceClient(
            account_url=f"https://{self.STORAGE_ACCOUNT}.blob.core.windows.net",
            credential=credential
        )
        self.container = self.blob_service.get_container_client(self.CONTAINER_NAME)
        
        # Load location reference data
        self.locations = self._load_locations()
    
    def _load_locations(self) -> Dict:
        """Load dispensary location coordinates from JSON."""
        import os
        locations_path = os.path.join(os.path.dirname(__file__), 'dispensary_locations.json')
        try:
            with open(locations_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load location data: {e}")
            return {}
    
    def _get_location_for_item(self, dispensary: str, store_location: str) -> Dict:
        """Get lat/lng/address for a store location."""
        if not store_location:
            return {'lat': None, 'lng': None, 'address': None}
        
        dispensary_locations = self.locations.get(dispensary.lower(), {})
        # Normalize store_location (remove special characters, lowercase)
        normalized_location = store_location.lower().replace(' ', '-').replace('_', '-')
        
        # Try exact match first
        location_data = dispensary_locations.get(normalized_location)
        if location_data:
            return location_data
        
        # Try without normalization
        location_data = dispensary_locations.get(store_location)
        if location_data:
            return location_data
        
        return {'lat': None, 'lng': None, 'address': None}
    
    @staticmethod
    def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance in miles using Haversine formula.
        
        Args:
            lat1, lng1: First coordinate pair
            lat2, lng2: Second coordinate pair
        
        Returns:
            Distance in miles
        """
        import math
        R = 3959  # Earth's radius in miles
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def normalize_strain_name(self, strain: str) -> str:
        """
        Normalize strain name for consistent indexing.
        
        Examples:
            'Blue Dream' -> 'bluedream'
            'OG Kush' -> 'ogkush'
            'Sour Diesel #4' -> 'sourdiesel4'
        """
        if not strain:
            return "unknown"
        
        # Lowercase
        name = strain.lower()
        # Remove special chars (keep letters, numbers, spaces)
        name = re.sub(r'[^a-z0-9\s]', '', name)
        # Remove extra whitespace
        name = re.sub(r'\s+', '', name)
        return name
    
    def build_index_from_date(self, date_str: str) -> Dict:
        """
        Build stock index from batch files for a specific date.
        
        Args:
            date_str: Date in YYYYMMDD format
        
        Returns:
            Complete stock index dictionary
        """
        logger.info(f"Building stock index for {date_str}...")
        
        # Find all batch files for this date
        prefix = f"batches/consolidated_{date_str}"
        batch_blobs = list(self.container.list_blobs(name_starts_with=prefix))
        
        if not batch_blobs:
            logger.warning(f"No batch files found for {date_str}")
            return self._empty_index()
        
        logger.info(f"Found {len(batch_blobs)} batch file(s)")
        
        # Process each batch file
        all_items: List[StockItem] = []
        for blob in batch_blobs:
            items = self._process_batch_file(blob.name)
            all_items.extend(items)
        
        # Build index structures
        return self._build_index_from_items(all_items, [blob.name for blob in batch_blobs])
    
    def build_index_from_latest(self) -> Dict:
        """Build stock index from the most recent consolidated batch file, plus menu files for missing dispensaries."""
        logger.info("Finding latest batch file...")
        
        # Known dispensaries we expect to have data for
        expected_dispensaries = {"trulieve", "muv", "flowery", "curaleaf", "cookies", "sunnyside", "sunburn"}
        
        # List all consolidated batch files
        batch_blobs = list(self.container.list_blobs(name_starts_with="batches/consolidated_"))
        
        if not batch_blobs:
            logger.warning("No batch files found, trying to build from menu files...")
            return self.build_index_from_menus()
        
        # Sort by name (which includes date) and get latest
        batch_blobs.sort(key=lambda b: b.name, reverse=True)
        latest_blob = batch_blobs[0]
        
        logger.info(f"Processing latest batch file: {latest_blob.name}")
        
        # Process the batch file
        items = self._process_batch_file(latest_blob.name)
        source_files = [latest_blob.name]
        
        # Check which dispensaries are in the batch data
        dispensaries_in_batch = {item.dispensary.lower() for item in items}
        missing_dispensaries = expected_dispensaries - dispensaries_in_batch
        
        if missing_dispensaries:
            logger.info(f"Dispensaries missing from batch: {missing_dispensaries}. Checking menu files...")
            
            # Try to fill in missing dispensaries from menu files
            for dispensary in missing_dispensaries:
                menu_items = self._get_latest_menu_items(dispensary)
                if menu_items:
                    items.extend(menu_items)
                    logger.info(f"Added {len(menu_items)} items from {dispensary} menu files")
        
        # Build index
        return self._build_index_from_items(items, source_files)
    
    def _get_latest_menu_items(self, dispensary: str, max_days_back: int = 30) -> List[StockItem]:
        """Get items from the most recent menu file for a dispensary, looking back up to max_days_back days."""
        from datetime import timedelta
        
        for days_back in range(max_days_back):
            check_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            date_str = check_date.strftime("%Y/%m/%d")
            prefix = f"dispensaries/{dispensary}/{date_str}/"
            
            menu_blobs = list(self.container.list_blobs(name_starts_with=prefix))
            
            if menu_blobs:
                # Get the latest file
                menu_blobs.sort(key=lambda b: b.name, reverse=True)
                latest_menu = menu_blobs[0]
                
                logger.info(f"Found menu file for {dispensary}: {latest_menu.name} ({days_back} days old)")
                return self._process_menu_file(latest_menu.name, dispensary)
        
        logger.warning(f"No menu files found for {dispensary} in last {max_days_back} days")
        return []
    
    def build_index_from_menus(self) -> Dict:
        """Build stock index directly from raw menu files (fallback if no batch files)."""
        logger.info("Building stock index from menu files...")
        
        # Get today's date
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        
        # Known dispensary folders
        dispensaries = ["trulieve", "muv", "flowery", "curaleaf", "cookies", "sunnyside", "sunburn"]
        
        all_items: List[StockItem] = []
        source_files: List[str] = []
        
        for dispensary in dispensaries:
            # Look for today's menu files
            prefix = f"dispensaries/{dispensary}/{today}/"
            menu_blobs = list(self.container.list_blobs(name_starts_with=prefix))
            
            if not menu_blobs:
                # Try yesterday
                from datetime import timedelta
                yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y/%m/%d")
                prefix = f"dispensaries/{dispensary}/{yesterday}/"
                menu_blobs = list(self.container.list_blobs(name_starts_with=prefix))
            
            if menu_blobs:
                # Get the latest file for this dispensary
                menu_blobs.sort(key=lambda b: b.name, reverse=True)
                latest_menu = menu_blobs[0]
                
                logger.info(f"Processing menu for {dispensary}: {latest_menu.name}")
                items = self._process_menu_file(latest_menu.name, dispensary)
                all_items.extend(items)
                source_files.append(latest_menu.name)
        
        if not all_items:
            logger.warning("No menu files found")
            return self._empty_index()
        
        return self._build_index_from_items(all_items, source_files)
    
    def _process_menu_file(self, blob_name: str, dispensary: str) -> List[StockItem]:
        """Process a raw menu file and extract stock items."""
        try:
            blob_client = self.container.get_blob_client(blob_name)
            content = blob_client.download_blob().readall()
            data = json.loads(content)
            
            items = []
            
            # Handle different menu formats
            products = []
            
            # Common product array locations
            if isinstance(data, list):
                products = data
            elif 'products' in data:
                products = data['products']
            elif 'data' in data:
                if isinstance(data['data'], list):
                    products = data['data']
                elif 'products' in data['data']:
                    products = data['data']['products']
            elif 'items' in data:
                products = data['items']
            elif 'menu' in data:
                products = data['menu']
            
            for product in products:
                if not isinstance(product, dict):
                    continue
                
                # Extract strain name (various field names)
                strain = (
                    product.get('strain') or 
                    product.get('strainName') or 
                    product.get('strain_name') or
                    product.get('name') or 
                    product.get('productName') or
                    product.get('title') or
                    'Unknown'
                )
                
                # Extract batch number
                batch_id = (
                    product.get('batch_number') or
                    product.get('batchNumber') or
                    product.get('batchId') or
                    product.get('batch_id') or
                    product.get('sku') or
                    product.get('id') or
                    'unknown'
                )
                
                # Extract category
                category = (
                    product.get('category') or
                    product.get('productCategory') or
                    product.get('product_category') or
                    product.get('type') or
                    'unknown'
                )
                
                # Extract THC/CBD
                thc = product.get('thc') or product.get('thcPercent') or product.get('thc_percent')
                cbd = product.get('cbd') or product.get('cbdPercent') or product.get('cbd_percent')
                
                # Try to convert to float
                try:
                    thc = float(thc) if thc else None
                except (ValueError, TypeError):
                    thc = None
                try:
                    cbd = float(cbd) if cbd else None
                except (ValueError, TypeError):
                    cbd = None
                
                item = StockItem(
                    batch_id=str(batch_id),
                    strain=strain,
                    strain_normalized=self.normalize_strain_name(strain),
                    dispensary=dispensary,
                    category=str(category) if category else 'unknown',
                    product_name=product.get('name') or strain,
                    thc_percent=thc,
                    cbd_percent=cbd,
                    terpenes=product.get('terpenes'),
                    price=product.get('price'),
                    last_seen=datetime.now(timezone.utc).isoformat(),
                    source_file=blob_name
                )
                
                items.append(item)
            
            logger.info(f"Extracted {len(items)} items from {blob_name}")
            return items
            
        except Exception as e:
            logger.error(f"Error processing menu file {blob_name}: {e}")
            return []
    
    def _process_batch_file(self, blob_name: str) -> List[StockItem]:
        """Process a single batch file and extract stock items."""
        blob_client = self.container.get_blob_client(blob_name)
        content = blob_client.download_blob().readall()
        data = json.loads(content)
        
        items = []
        
        # Process each batch in the file
        for batch in data.get('batches', []):
            dispensary = batch.get('dispensary', 'unknown')
            
            # Extract strain name - batch files use 'strain' field
            # Also check 'strain_name' for compatibility
            strain = (
                batch.get('strain') or 
                batch.get('strain_name') or 
                batch.get('product_name') or 
                batch.get('name', 'Unknown')
            )
            
            # Extract batch ID - can be batch_code, batch_number, or batch_name
            batch_id = (
                batch.get('batch_code') or
                batch.get('batch_number') or
                batch.get('batch_name') or
                'unknown'
            )
            
            # Get category from product_type or category field
            category = batch.get('category') or batch.get('product_type') or 'unknown'
            
            item = StockItem(
                batch_id=batch_id,
                strain=strain,
                strain_normalized=self.normalize_strain_name(strain),
                dispensary=dispensary,
                category=category,
                product_name=batch.get('product_name') or batch.get('name') or strain,
                thc_percent=batch.get('thc_percent'),
                cbd_percent=batch.get('cbd_percent'),
                terpenes=batch.get('terpenes'),
                last_seen=batch.get('last_updated') or datetime.now(timezone.utc).isoformat(),
                source_file=blob_name
            )
            
            items.append(item)
        
        logger.info(f"Extracted {len(items)} items from {blob_name}")
        return items
    
    def _build_index_from_items(self, items: List[StockItem], source_files: List[str]) -> Dict:
        """Build complete index structure from stock items."""
        
        # By strain (normalized)
        by_strain: Dict[str, List[StockItem]] = defaultdict(list)
        for item in items:
            by_strain[item.strain_normalized].append(item)
        
        # By dispensary
        by_dispensary: Dict[str, List[StockItem]] = defaultdict(list)
        for item in items:
            by_dispensary[item.dispensary].append(item)
        
        # By category
        by_category: Dict[str, List[StockItem]] = defaultdict(list)
        for item in items:
            by_category[item.category].append(item)
        
        # Full list (sorted by strain, then dispensary)
        items_sorted = sorted(items, key=lambda x: (x.strain_normalized, x.dispensary))
        
        # Metadata
        dispensaries = list(by_dispensary.keys())
        unique_strains = len(by_strain)
        
        metadata = IndexMetadata(
            build_date=datetime.now(timezone.utc).isoformat(),
            total_items=len(items),
            dispensaries=dispensaries,
            unique_strains=unique_strains,
            batch_files_processed=len(source_files),
            source_date_range={
                "earliest": min(source_files) if source_files else None,
                "latest": max(source_files) if source_files else None
            }
        )
        
        # Build complete index
        index = {
            "metadata": asdict(metadata),
            "items": [asdict(item) for item in items_sorted],
            "by_strain": {k: [asdict(item) for item in v] for k, v in by_strain.items()},
            "by_dispensary": {k: [asdict(item) for item in v] for k, v in by_dispensary.items()},
            "by_category": {k: [asdict(item) for item in v] for k, v in by_category.items()},
        }
        
        logger.info(f"Index built: {len(items)} items, {unique_strains} strains, {len(dispensaries)} dispensaries")
        
        return index
    
    def _empty_index(self) -> Dict:
        """Return an empty index structure."""
        metadata = IndexMetadata(
            build_date=datetime.now(timezone.utc).isoformat(),
            total_items=0,
            dispensaries=[],
            unique_strains=0,
            batch_files_processed=0,
            source_date_range={"earliest": None, "latest": None}
        )
        
        return {
            "metadata": asdict(metadata),
            "items": [],
            "by_strain": {},
            "by_dispensary": {},
            "by_category": {},
        }
    
    def save_index(self, index: Dict) -> str:
        """
        Save index to blob storage.
        
        Saves:
        - stock-index/current.json (full index)
        - stock-index/metadata.json (metadata only)
        
        Returns:
            Path to saved index
        """
        current_path = f"{self.INDEX_PREFIX}/current.json"
        metadata_path = f"{self.INDEX_PREFIX}/metadata.json"
        
        # Save full index
        blob_client = self.container.get_blob_client(current_path)
        content = json.dumps(index, indent=2)
        blob_client.upload_blob(content, overwrite=True)
        logger.info(f"Saved full index to {current_path}")
        
        # Save metadata separately
        metadata_blob = self.container.get_blob_client(metadata_path)
        metadata_content = json.dumps(index['metadata'], indent=2)
        metadata_blob.upload_blob(metadata_content, overwrite=True)
        logger.info(f"Saved metadata to {metadata_path}")
        
        # Save timestamp
        timestamp_path = f"{self.INDEX_PREFIX}/last_updated.txt"
        timestamp_blob = self.container.get_blob_client(timestamp_path)
        timestamp_blob.upload_blob(
            datetime.now(timezone.utc).isoformat(),
            overwrite=True
        )
        
        return current_path
    
    def get_index(self) -> Optional[Dict]:
        """Load the current stock index from storage."""
        try:
            path = f"{self.INDEX_PREFIX}/current.json"
            blob_client = self.container.get_blob_client(path)
            content = blob_client.download_blob().readall()
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load stock index: {e}")
            return None


def main():
    """Build stock index from latest batch files."""
    logging.basicConfig(level=logging.INFO)
    
    indexer = StockIndexer()
    
    # Build from latest
    index = indexer.build_index_from_latest()
    
    # Save
    indexer.save_index(index)
    
    print(f"\n=== Stock Index Built ===")
    print(f"Total items: {index['metadata']['total_items']}")
    print(f"Unique strains: {index['metadata']['unique_strains']}")
    print(f"Dispensaries: {', '.join(index['metadata']['dispensaries'])}")
    print(f"Build date: {index['metadata']['build_date']}")


if __name__ == "__main__":
    main()
