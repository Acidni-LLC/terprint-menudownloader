"""
Extract strain genetics from Curaleaf COA (Certificate of Analysis) PDFs
COA URLs are available in Curaleaf menu JSON files under 'lab_test_url' field
"""
import requests
import re
from typing import Optional, Dict
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
import json
from datetime import datetime, timedelta, timezone

class COAGeneticsExtractor:
    """Extract genetics from Curaleaf COA documents."""
    
    GENETICS_PATTERNS = [
        r'(?:Lineage|Genetics|Parents?):\s*([^x\n]+)\s*x\s*([^\n]+)',
        r'(?:Cross|Breeding):\s*([^x\n]+)\s*[xX]\s*([^\n]+)',
        r'Strain:\s*([^(]+)\(([^)]+)\)',  # Strain Name (Parent1 x Parent2)
    ]
    
    def __init__(self, storage_account="stterprintsharedgen2", container="jsonfiles"):
        self.credential = AzureCliCredential()
        self.blob_service = BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=self.credential
        )
        self.container = container
    
    def extract_from_coa_url(self, coa_url: str) -> Optional[Dict[str, str]]:
        """
        Extract genetics from COA PDF URL.
        Note: PDFs require parsing library like PyPDF2 or pdfplumber.
        For now, check if URL patterns reveal strain info.
        """
        if not coa_url or coa_url == "None":
            return None
        
        # Extract strain name from URL (many COAs have strain in filename)
        # Example: ...lab-results/Blue-Dream-COA.pdf
        url_strain = re.search(r'/([A-Za-z0-9-]+)[-_](?:COA|lab|test)', coa_url, re.I)
        if url_strain:
            strain_name = url_strain.group(1).replace('-', ' ').replace('_', ' ').title()
            return {'strain_name': strain_name, 'source': 'COA URL', 'coa_url': coa_url}
        
        return None
    
    def extract_from_menu_files(self, dispensary='curaleaf', max_files=20):
        """Extract COA URLs from recent Curaleaf menu files."""
        print(f"\n Extracting COA URLs from {dispensary} menu files...")
        
        container_client = self.blob_service.get_container_client(self.container)
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        prefix = f"dispensaries/{dispensary}/"
        
        blobs = [b for b in container_client.list_blobs(name_starts_with=prefix)
                 if b.last_modified >= cutoff and b.name.endswith('.json')]
        blobs = sorted(blobs, key=lambda b: b.last_modified, reverse=True)[:max_files]
        
        coa_genetics = []
        seen_strains = set()
        
        for blob in blobs:
            try:
                blob_client = self.blob_service.get_blob_client(self.container, blob.name)
                data = json.loads(blob_client.download_blob().readall())
                
                products = data.get('products', [])
                for product in products:
                    coa_url = product.get('lab_test_url')
                    if coa_url and coa_url != "None":
                        genetics = self.extract_from_coa_url(coa_url)
                        if genetics and genetics['strain_name'] not in seen_strains:
                            genetics['product_name'] = product.get('name', 'Unknown')
                            coa_genetics.append(genetics)
                            seen_strains.add(genetics['strain_name'])
                
                print(f"   {blob.name.split('/')[-1]}: {len(products)} products")
            except Exception as e:
                print(f"   {blob.name}: {e}")
        
        print(f"\n Found {len(coa_genetics)} unique COA URLs with strain names")
        return coa_genetics


if __name__ == "__main__":
    extractor = COAGeneticsExtractor()
    genetics = extractor.extract_from_menu_files(max_files=20)
    
    # Save results
    output = {
        'extraction_date': datetime.now().isoformat(),
        'source': 'Curaleaf COA URLs',
        'count': len(genetics),
        'genetics': genetics
    }
    
    filename = f"coa_genetics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n Saved to {filename}")
    
    # Print summary
    print("\n Sample COA Genetics:")
    for g in genetics[:10]:
        print(f"  {g['strain_name']} - {g['product_name'][:50]}")
