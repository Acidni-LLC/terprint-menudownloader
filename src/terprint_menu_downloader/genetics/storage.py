"""
Genetics Storage for Terprint Menu Downloader

Stores extracted genetics data to Azure Blob Storage in CDES-compatible format.
Uses the same storage structure as terprint-config/cannabis-genetics-scraper.

Storage Structure:
    genetics-data/
     index/strains-index.json      # Quick lookup index
     partitions/a.json             # Strains starting with 'a'
     partitions/b.json             # Strains starting with 'b'
     ...

Usage:
    from terprint_menu_downloader.genetics import GeneticsStorage
    
    storage = GeneticsStorage()
    await storage.save_genetics(genetics_list)
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import defaultdict

from .models import StrainGenetics, CDESGenetics

logger = logging.getLogger(__name__)

# Try to import Azure SDK
try:
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.identity import DefaultAzureCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    logger.warning("Azure Storage SDK not available. Install with: pip install azure-storage-blob azure-identity")


class GeneticsStorage:
    """
    Azure Blob Storage client for genetics data.
    
    Stores genetics in partitioned JSON files for efficient lookup:
    - index/strains-index.json: Quick lookup by slug
    - partitions/{a-z}.json: Full data by first letter
    
    Compatible with terprint-config GeneticsClient for reading.
    """
    
    CONTAINER_NAME = "genetics-data"
    INDEX_PATH = "index/strains-index.json"
    PARTITIONS_PATH = "partitions"
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        use_local_fallback: bool = True,
        local_dir: str = "./genetics_data"
    ):
        """
        Initialize genetics storage.
        
        Args:
            connection_string: Azure Storage connection string
            account_name: Storage account name (uses managed identity)
            use_local_fallback: Fall back to local files if Azure unavailable
            local_dir: Local directory for fallback storage
        """
        self._connection_string = connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self._account_name = account_name or os.environ.get("GENETICS_STORAGE_ACCOUNT", "stterprintsharedgen2")
        self._use_local = use_local_fallback
        self._local_dir = local_dir
        
        self._client: Optional[BlobServiceClient] = None
        self._container: Optional[ContainerClient] = None
        self._index: Optional[Dict] = None
        self._partitions: Dict[str, Dict] = {}
        self._modified_partitions: set = set()
    
    async def connect(self) -> bool:
        """
        Initialize Azure Blob connection.
        
        Returns:
            True if connected successfully, False if using local fallback
        """
        if not AZURE_AVAILABLE:
            logger.warning("Azure SDK not available, using local storage")
            return False
        
        try:
            if self._connection_string:
                self._client = BlobServiceClient.from_connection_string(self._connection_string)
                logger.info("Connected to Azure Blob via connection string")
            else:
                account_url = f"https://{self._account_name}.blob.core.windows.net"
                credential = DefaultAzureCredential()
                self._client = BlobServiceClient(account_url=account_url, credential=credential)
                logger.info(f"Connected to Azure Blob via managed identity: {self._account_name}")
            
            self._container = self._client.get_container_client(self.CONTAINER_NAME)
            
            # Create container if needed
            try:
                self._container.create_container()
                logger.info(f"Created container: {self.CONTAINER_NAME}")
            except Exception:
                pass  # Container exists
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Azure: {e}")
            if self._use_local:
                logger.info(f"Falling back to local storage: {self._local_dir}")
            return False
    
    def _get_partition_key(self, strain_slug: str) -> str:
        """Get partition key (first letter) for a strain slug."""
        if not strain_slug:
            return "other"
        first_char = strain_slug[0].lower()
        if first_char.isalpha():
            return first_char
        return "other"
    
    async def load_index(self) -> Dict:
        """Load the strain index from storage."""
        if self._index is not None:
            return self._index
        
        try:
            if self._container:
                blob = self._container.get_blob_client(self.INDEX_PATH)
                if blob.exists():
                    content = blob.download_blob().readall()
                    self._index = json.loads(content)
                    logger.info(f"Loaded index: {self._index.get('total_strains', 0)} strains")
                    return self._index
            
            # Try local
            if self._use_local:
                local_path = os.path.join(self._local_dir, self.INDEX_PATH)
                if os.path.exists(local_path):
                    with open(local_path) as f:
                        self._index = json.load(f)
                    return self._index
        
        except Exception as e:
            logger.warning(f"Could not load index: {e}")
        
        # Return empty index
        self._index = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_strains": 0,
            "partitions": [],
            "strains": {}
        }
        return self._index
    
    async def load_partition(self, partition_key: str) -> Dict:
        """Load a partition file from storage."""
        if partition_key in self._partitions:
            return self._partitions[partition_key]
        
        partition_path = f"{self.PARTITIONS_PATH}/{partition_key}.json"
        
        try:
            if self._container:
                blob = self._container.get_blob_client(partition_path)
                if blob.exists():
                    content = blob.download_blob().readall()
                    self._partitions[partition_key] = json.loads(content)
                    return self._partitions[partition_key]
            
            # Try local
            if self._use_local:
                local_path = os.path.join(self._local_dir, partition_path)
                if os.path.exists(local_path):
                    with open(local_path) as f:
                        self._partitions[partition_key] = json.load(f)
                    return self._partitions[partition_key]
        
        except Exception as e:
            logger.warning(f"Could not load partition {partition_key}: {e}")
        
        # Return empty partition
        self._partitions[partition_key] = {"strains": []}
        return self._partitions[partition_key]
    
    async def save_genetics(
        self,
        genetics: List[StrainGenetics],
        merge: bool = True
    ) -> Dict[str, Any]:
        """
        Save genetics data to storage.
        
        Args:
            genetics: List of StrainGenetics to save
            merge: If True, merge with existing data; if False, overwrite
            
        Returns:
            Dict with save statistics
        """
        stats = {
            "total": len(genetics),
            "new": 0,
            "updated": 0,
            "partitions_modified": set(),
            "errors": []
        }
        
        # Load current index
        index = await self.load_index()
        
        # Group by partition
        by_partition: Dict[str, List[StrainGenetics]] = defaultdict(list)
        for g in genetics:
            key = self._get_partition_key(g.strain_slug)
            by_partition[key].append(g)
        
        # Process each partition
        for partition_key, partition_genetics in by_partition.items():
            try:
                partition = await self.load_partition(partition_key)
                
                # Build lookup by slug
                existing = {s["strain_slug"]: s for s in partition.get("strains", [])}
                
                for g in partition_genetics:
                    if g.strain_slug in existing:
                        if merge:
                            # Update existing
                            existing[g.strain_slug].update(g.to_dict())
                            stats["updated"] += 1
                        # else skip
                    else:
                        # Add new
                        existing[g.strain_slug] = g.to_dict()
                        stats["new"] += 1
                        
                        # Update index
                        index["strains"][g.strain_slug] = {
                            "name": g.strain_name,
                            "partition": partition_key,
                            "has_lineage": bool(g.parent_1 and g.parent_2)
                        }
                
                # Update partition
                partition["strains"] = list(existing.values())
                partition["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._partitions[partition_key] = partition
                self._modified_partitions.add(partition_key)
                stats["partitions_modified"].add(partition_key)
                
            except Exception as e:
                logger.error(f"Error processing partition {partition_key}: {e}")
                stats["errors"].append(f"{partition_key}: {str(e)}")
        
        # Update index metadata
        index["total_strains"] = len(index["strains"])
        index["updated_at"] = datetime.now(timezone.utc).isoformat()
        index["partitions"] = sorted(self._modified_partitions)
        self._index = index
        
        # Persist changes
        await self._save_changes()
        
        stats["partitions_modified"] = list(stats["partitions_modified"])
        return stats
    
    async def _save_changes(self):
        """Save modified partitions and index to storage."""
        
        # Save to Azure
        if self._container:
            try:
                # Save modified partitions
                for partition_key in self._modified_partitions:
                    partition_path = f"{self.PARTITIONS_PATH}/{partition_key}.json"
                    content = json.dumps(self._partitions[partition_key], indent=2)
                    blob = self._container.get_blob_client(partition_path)
                    blob.upload_blob(content, overwrite=True)
                    logger.debug(f"Saved partition: {partition_path}")
                
                # Save index
                content = json.dumps(self._index, indent=2)
                blob = self._container.get_blob_client(self.INDEX_PATH)
                blob.upload_blob(content, overwrite=True)
                logger.info(f"Saved index with {self._index['total_strains']} strains")
                
                self._modified_partitions.clear()
                return
                
            except Exception as e:
                logger.error(f"Failed to save to Azure: {e}")
        
        # Fallback to local
        if self._use_local:
            try:
                os.makedirs(os.path.join(self._local_dir, self.PARTITIONS_PATH), exist_ok=True)
                os.makedirs(os.path.join(self._local_dir, "index"), exist_ok=True)
                
                # Save modified partitions
                for partition_key in self._modified_partitions:
                    partition_path = os.path.join(self._local_dir, self.PARTITIONS_PATH, f"{partition_key}.json")
                    with open(partition_path, 'w') as f:
                        json.dump(self._partitions[partition_key], f, indent=2)
                    logger.debug(f"Saved partition locally: {partition_path}")
                
                # Save index
                index_path = os.path.join(self._local_dir, self.INDEX_PATH)
                with open(index_path, 'w') as f:
                    json.dump(self._index, f, indent=2)
                logger.info(f"Saved index locally: {index_path}")
                
                self._modified_partitions.clear()
                
            except Exception as e:
                logger.error(f"Failed to save locally: {e}")

    async def refresh_index(self) -> Dict[str, Any]:
        """Rebuild the quick lookup index from all partitions and persist it.
        Returns the refreshed index dict.
        """
        refreshed = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_strains": 0,
            "partitions": [],
            "strains": {}
        }

        partition_keys: List[str] = []

        # Discover partition keys
        try:
            if self._container:
                for blob in self._container.list_blobs(name_starts_with=self.PARTITIONS_PATH + "/"):
                    name = getattr(blob, "name", "")
                    if name.endswith(".json"):
                        key = os.path.splitext(os.path.basename(name))[0]
                        partition_keys.append(key)
            elif self._use_local:
                local_partitions_dir = os.path.join(self._local_dir, self.PARTITIONS_PATH)
                if os.path.isdir(local_partitions_dir):
                    for fname in os.listdir(local_partitions_dir):
                        if fname.endswith(".json"):
                            partition_keys.append(os.path.splitext(fname)[0])
        except Exception as e:
            logger.warning(f"[INDEX] Could not enumerate partitions: {e}")

        partition_keys = sorted(set(partition_keys))
        refreshed["partitions"] = partition_keys

        # Load each partition and populate index
        for key in partition_keys:
            try:
                part = await self.load_partition(key)
                for s in part.get("strains", []):
                    slug = s.get("strain_slug")
                    if not slug:
                        continue
                    refreshed["strains"][slug] = {
                        "name": s.get("strain_name"),
                        "partition": key,
                        "has_lineage": bool(s.get("parent_1") and s.get("parent_2"))
                    }
            except Exception as e:
                logger.debug(f"[INDEX] Skipping partition {key}: {e}")

        refreshed["total_strains"] = len(refreshed["strains"]) 
        self._index = refreshed

        # Persist index without requiring modified partitions
        self._modified_partitions.clear()
        await self._save_changes()
        logger.info(f"[INDEX] Refreshed index with {refreshed['total_strains']} strains across {len(partition_keys)} partitions")
        return refreshed
    
    async def get_strain(self, strain_name: str) -> Optional[Dict]:
        """
        Get genetics data for a strain by name.
        
        Args:
            strain_name: Strain name to look up
            
        Returns:
            Strain genetics dict or None
        """
        slug = StrainGenetics.normalize_strain_name(strain_name)
        
        index = await self.load_index()
        if slug not in index.get("strains", {}):
            return None
        
        partition_key = index["strains"][slug].get("partition", self._get_partition_key(slug))
        partition = await self.load_partition(partition_key)
        
        for strain in partition.get("strains", []):
            if strain.get("strain_slug") == slug:
                return strain
        
        return None
    
    async def get_lineage(self, strain_name: str) -> Optional[tuple]:
        """
        Get parent strains for a strain.
        
        Args:
            strain_name: Strain name
            
        Returns:
            Tuple of (parent_1, parent_2) or None
        """
        strain = await self.get_strain(strain_name)
        if strain and strain.get("parent_1") and strain.get("parent_2"):
            return (strain["parent_1"], strain["parent_2"])
        return None
    
    async def get_stats(self) -> Dict:
        """Get statistics about the genetics database."""
        index = await self.load_index()
        return {
            "total_strains": index.get("total_strains", 0),
            "partitions": len(index.get("partitions", [])),
            "updated_at": index.get("updated_at"),
            "strains_with_lineage": sum(
                1 for s in index.get("strains", {}).values()
                if s.get("has_lineage")
            )
        }
    
    def to_cdes_genetics(self, strain: StrainGenetics) -> CDESGenetics:
        """Convert StrainGenetics to CDES format."""
        return CDESGenetics.from_strain_genetics(strain)
