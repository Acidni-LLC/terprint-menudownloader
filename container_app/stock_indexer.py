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
        """Build stock index from the most recent consolidated batch file."""
        logger.info("Finding latest batch file...")
        
        # List all consolidated batch files
        batch_blobs = list(self.container.list_blobs(name_starts_with="batches/consolidated_"))
        
        if not batch_blobs:
            logger.warning("No batch files found")
            return self._empty_index()
        
        # Sort by name (which includes date) and get latest
        batch_blobs.sort(key=lambda b: b.name, reverse=True)
        latest_blob = batch_blobs[0]
        
        logger.info(f"Processing latest batch file: {latest_blob.name}")
        
        # Process the file
        items = self._process_batch_file(latest_blob.name)
        
        # Build index
        return self._build_index_from_items(items, [latest_blob.name])
    
    def _process_batch_file(self, blob_name: str) -> List[StockItem]:
        """Process a single batch file and extract stock items."""
        blob_client = self.container.get_blob_client(blob_name)
        content = blob_client.download_blob().readall()
        data = json.loads(content)
        
        items = []
        
        # Process each batch in the file
        for batch in data.get('batches', []):
            dispensary = batch.get('dispensary', 'unknown')
            
            # Extract stock item
            strain = batch.get('strain_name') or batch.get('name', 'Unknown')
            
            item = StockItem(
                batch_id=batch.get('batch_number', 'unknown'),
                strain=strain,
                strain_normalized=self.normalize_strain_name(strain),
                dispensary=dispensary,
                category=batch.get('category', 'unknown'),
                product_name=batch.get('name', strain),
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
