"""
Extract genetics from product descriptions and metadata in menu JSON files
Many dispensaries include genetics in product descriptions like:
"Blue Dream is a cross of Blueberry and Haze"
"""
import re
import json
from typing import List, Dict, Optional
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
from datetime import datetime, timedelta, timezone


class MenuDescriptionGeneticsExtractor:
    """Extract genetics from product descriptions in menu JSON files."""
    
    GENETICS_PATTERNS = [
        # "cross of X and Y" or "cross between X and Y"
        r'cross\s+(?:of|between)\s+([^,\n]+?)\s+(?:and|&|x)\s+([^,\.\n]+)',
        # "X x Y" format
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[xX]\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        # "hybrid of X and Y"
        r'hybrid\s+of\s+([^,\n]+?)\s+(?:and|&)\s+([^,\.\n]+)',
        # "blend of X and Y"
        r'blend\s+of\s+([^,\n]+?)\s+(?:and|&)\s+([^,\.\n]+)',
        # "(X x Y)"
        r'\(([^)]+?)\s+[xX]\s+([^)]+?)\)',
        # "descended from X and Y"
        r'descended\s+from\s+([^,\n]+?)\s+(?:and|&)\s+([^,\.\n]+)',
        # "bred from X and Y"
        r'bred\s+from\s+([^,\n]+?)\s+(?:and|&)\s+([^,\.\n]+)',
    ]
    
    def __init__(self, storage_account="stterprintsharedgen2", container="jsonfiles"):
        self.credential = AzureCliCredential()
        self.blob_service = BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=self.credential
        )
        self.container = container
    
    def extract_genetics(self, text: str) -> Optional[tuple]:
        """Extract parent strains from text description."""
        if not text:
            return None
        
        text = text.lower()
        
        for pattern in self.GENETICS_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parent1 = match.group(1).strip().title()
                parent2 = match.group(2).strip().title()
                
                # Clean up common suffixes
                for suffix in [' strain', ' cannabis', ' marijuana']:
                    parent1 = parent1.replace(suffix, '').strip()
                    parent2 = parent2.replace(suffix, '').strip()
                
                return (parent1, parent2)
        
        return None
    
    def extract_from_menu(self, menu_data: dict, dispensary: str) -> List[Dict]:
        """Extract genetics from all products in a menu file."""
        genetics = []
        products = menu_data.get('products', [])
        
        # Handle different menu structures
        if isinstance(products, dict):
            if 'list' in products:
                products = products['list']
            elif 'results' in products:
                products = products['results']
        
        for product in products:
            if not isinstance(product, dict):
                continue
            
            strain_name = product.get('name', '').strip()
            if not strain_name:
                continue
            
            # Check description field (different dispensaries use different field names)
            description_fields = ['description', 'desc', 'info', 'details', 'notes', 'strain_info']
            description = ''
            
            for field in description_fields:
                if field in product:
                    description = product.get(field, '')
                    if description:
                        break
            
            if description:
                parents = self.extract_genetics(description)
                if parents:
                    genetics.append({
                        'strain_name': strain_name,
                        'parent1': parents[0],
                        'parent2': parents[1],
                        'dispensary': dispensary,
                        'source': 'Menu Description',
                        'description_snippet': description[:200]
                    })
        
        return genetics
    
    def scan_dispensary(self, dispensary: str, max_files: int = 20):
        """Scan recent menu files for a dispensary."""
        print(f"\n Scanning {dispensary} menu descriptions...")
        
        container_client = self.blob_service.get_container_client(self.container)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        prefix = f"dispensaries/{dispensary}/"
        
        blobs = [b for b in container_client.list_blobs(name_starts_with=prefix)
                 if b.last_modified >= cutoff and b.name.endswith('.json')]
        blobs = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[:max_files]
        
        all_genetics = []
        seen_strains = set()
        
        for blob in blobs:
            try:
                blob_client = self.blob_service.get_blob_client(self.container, blob.name)
                data = json.loads(blob_client.download_blob().readall())
                
                genetics = self.extract_from_menu(data, dispensary)
                
                # Deduplicate
                for g in genetics:
                    if g['strain_name'] not in seen_strains:
                        all_genetics.append(g)
                        seen_strains.add(g['strain_name'])
                
                if genetics:
                    print(f"   {blob.name.split('/')[-1]}: {len(genetics)} genetics found")
                else:
                    print(f"  - {blob.name.split('/')[-1]}: 0 genetics")
                    
            except Exception as e:
                print(f"   {blob.name}: {e}")
        
        print(f"\n Total unique genetics from {dispensary}: {len(all_genetics)}")
        return all_genetics


if __name__ == "__main__":
    extractor = MenuDescriptionGeneticsExtractor()
    
    dispensaries = ['curaleaf', 'muv', 'cookies', 'flowery', 'trulieve']
    all_genetics = []
    
    for dispensary in dispensaries:
        genetics = extractor.scan_dispensary(dispensary, max_files=10)
        all_genetics.extend(genetics)
    
    # Save results
    output = {
        'extraction_date': datetime.now().isoformat(),
        'source': 'Menu Product Descriptions',
        'total_count': len(all_genetics),
        'by_dispensary': {},
        'genetics': all_genetics
    }
    
    # Count by dispensary
    for g in all_genetics:
        disp = g['dispensary']
        output['by_dispensary'][disp] = output['by_dispensary'].get(disp, 0) + 1
    
    filename = f"menu_description_genetics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n Saved to {filename}")
    print(f"\n Total genetics extracted: {len(all_genetics)}")
    print("\nBreakdown by dispensary:")
    for disp, count in sorted(output['by_dispensary'].items()):
        print(f"  {disp}: {count}")
    
    # Show samples
    print("\n Sample genetics found:")
    for g in all_genetics[:10]:
        print(f"  {g['strain_name']} = {g['parent1']} x {g['parent2']}")
