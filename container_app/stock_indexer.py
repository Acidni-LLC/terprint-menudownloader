"""
Stock Index Builder

Builds searchable stock index from SQL database (Batch table).
Reads enriched product data after COA Processor runs.

Data Source: Azure SQL Database (terprint.Batch table)
- Enriched with terpene profiles, cannabinoid percentages
- Includes pricing, weights, store locations
- Updated 3x daily after batch processing runs

Copyright (c) 2026 Acidni LLC
"""

import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import pymssql

logger = logging.getLogger(__name__)


@dataclass
class StockItem:
    """A product in stock with full enriched data from database."""
    batch_id: str
    strain: str
    strain_normalized: str
    dispensary: str
    category: str
    product_name: str
    
    # Cannabis data (from COA Processor)
    thc_percent: Optional[float] = None
    cbd_percent: Optional[float] = None
    cbg_percent: Optional[float] = None
    thca_percent: Optional[float] = None
    cbda_percent: Optional[float] = None
    terpenes: Optional[Dict[str, float]] = None
    terpenes_total: Optional[float] = None
    
    # Pricing/availability (from menu data)
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
    source: str = "database"  # "database" or "blob_storage"
    source: str = "database"  # Always "database" now


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
    Builds searchable stock index from SQL database.
    
    Data Source: Azure SQL Database (terprint.Batch table)
    - Enriched with COA data (terpenes, cannabinoids)
    - Includes pricing, weights, locations
    - Only returns in-stock items
    
    Usage:
        indexer = StockIndexer()
        
        # Build from current database state
        index = indexer.build_index_from_database()
        
        # Get stock for specific dispensary
        cookies_stock = indexer.get_dispensary_stock('cookies')
        
        # Search by strain name
        results = indexer.search_by_strain('blue dream', lat=28.5, lng=-81.3)
    """
    
    # SQL Connection (use pymssql for Azure Functions Linux)
    SQL_SERVER = "acidni-sql.database.windows.net"
    SQL_DATABASE = "terprint"
    SQL_USER = "adm"
    SQL_PASSWORD = "sql1234%"  # Default - override with environment variable
    
    def __init__(self):
        # Load SQL password from environment (override default)
        self.sql_password = os.environ.get('SQL_PASSWORD', self.SQL_PASSWORD)
        
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
    
    def _get_db_connection(self):
        """Get database connection using pymssql."""
        try:
            conn = pymssql.connect(
                server=self.SQL_SERVER,
                user=self.SQL_USER,
                password=self.sql_password,
                database=self.SQL_DATABASE,
                port=1433,
                timeout=30
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def build_index_from_database(self, dispensary: str = None, max_age_days: int = 7) -> Dict:
        """
        Build stock index from SQL database.
        
        Args:
            dispensary: Optional - filter by specific dispensary
            max_age_days: Only include items seen in last N days (default: 7)
        
        Returns:
            Complete stock index dictionary with enriched product data
        """
        logger.info(f"Building stock index from database (dispensary={dispensary}, max_age_days={max_age_days})...")
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor(as_dict=True)
            
            # Query enriched batch data from database
            # Note: Using %s placeholders for pymssql (not ? like pyodbc)
            query = """
            SELECT 
                BatchId,
                ProductName,
                Strain,
                Dispensary,
                Category,
                ThcPercent,
                CbdPercent,
                CbgPercent,
                ThcaPercent,
                CbdaPercent,
                Terpenes,
                TerpenesTotal,
                Price,
                WeightGrams,
                InStock,
                StoreLocation,
                StoreName,
                Latitude,
                Longitude,
                Address,
                LastSeen,
                ProcessedDate
            FROM Batch
            WHERE InStock = 1
                AND LastSeen >= DATEADD(day, %s, GETDATE())
            """
            
            params = [-max_age_days]
            
            if dispensary:
                query += " AND LOWER(Dispensary) = %s"
                params.append(dispensary.lower())
            
            query += " ORDER BY LastSeen DESC"
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            logger.info(f"Retrieved {len(rows)} in-stock items from database")
            
            # Build stock items
            stock_items = []
            dispensaries_set = set()
            strains_set = set()
            
            for row in rows:
                # Parse terpenes JSON if present
                terpenes_dict = None
                if row.get('Terpenes'):
                    try:
                        terpenes_dict = json.loads(row['Terpenes'])
                    except:
                        logger.warning(f"Failed to parse terpenes for {row.get('BatchId')}")
                
                # Create stock item
                item = StockItem(
                    batch_id=row.get('BatchId', ''),
                    strain=row.get('Strain', 'Unknown'),
                    strain_normalized=self.normalize_strain_name(row.get('Strain', '')),
                    dispensary=row.get('Dispensary', '').lower(),
                    category=row.get('Category', ''),
                    product_name=row.get('ProductName', ''),
                    thc_percent=float(row['ThcPercent']) if row.get('ThcPercent') else None,
                    cbd_percent=float(row['CbdPercent']) if row.get('CbdPercent') else None,
                    cbg_percent=float(row['CbgPercent']) if row.get('CbgPercent') else None,
                    thca_percent=float(row['ThcaPercent']) if row.get('ThcaPercent') else None,
                    cbda_percent=float(row['CbdaPercent']) if row.get('CbdaPercent') else None,
                    terpenes=terpenes_dict,
                    terpenes_total=float(row['TerpenesTotal']) if row.get('TerpenesTotal') else None,
                    price=float(row['Price']) if row.get('Price') else None,
                    weight_grams=float(row['WeightGrams']) if row.get('WeightGrams') else None,
                    in_stock=True,
                    store_location=row.get('StoreLocation'),
                    store_name=row.get('StoreName'),
                    latitude=float(row['Latitude']) if row.get('Latitude') else None,
                    longitude=float(row['Longitude']) if row.get('Longitude') else None,
                    address=row.get('Address'),
                    last_seen=row.get('LastSeen').isoformat() if row.get('LastSeen') else None,
                    source="database"
                )
                
                stock_items.append(item)
                dispensaries_set.add(item.dispensary)
                strains_set.add(item.strain_normalized)
            
            cursor.close()
            conn.close()
            
            # Build index structure
            index = {
                "metadata": {
                    "build_date": datetime.now(timezone.utc).isoformat(),
                    "total_items": len(stock_items),
                    "dispensaries": sorted(list(dispensaries_set)),
                    "unique_strains": len(strains_set),
                    "source": "database",
                    "max_age_days": max_age_days
                },
                "items": [asdict(item) for item in stock_items],
                "by_dispensary": self._group_by_dispensary(stock_items),
                "by_strain": self._group_by_strain(stock_items)
            }
            
            logger.info(f"Stock index built: {len(stock_items)} items, {len(strains_set)} unique strains")
            return index
            
        except Exception as e:
            logger.error(f"Failed to build index from database: {e}")
            return self._empty_index()
    
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
