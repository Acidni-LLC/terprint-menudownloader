"""
Extract product URLs from menu JSON files for web scraping
"""
import json
import asyncio
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
from typing import List, Dict
from datetime import datetime, timedelta
import re


class ProductURLExtractor:
    """Extract product URLs from menu JSON files stored in Azure."""
    
    DISPENSARY_URL_PATTERNS = {
        'trulieve': 'https://www.trulieve.com/dispensary-near-me/florida/products/{slug}',
        'muv': 'https://www.muvfl.com/products/{slug}',
        'cookies': 'https://cookies.co/dispensaries/florida/{location}/menu/{slug}',
        'curaleaf': 'https://shop.curaleaf.com/store/{location}/product/{slug}',
        'flowery': 'https://shop.theflowery.co/products/{slug}'
    }
    
    def __init__(self, storage_account="stterprintsharedgen2", container="jsonfiles"):
        self.credential = AzureCliCredential()
        self.blob_service = BlobServiceClient(
            account_url=f"https://{storage_account}.blob.core.windows.net",
            credential=self.credential
        )
        self.container = container
    
    def slugify(self, name: str) -> str:
        """Convert product name to URL slug."""
        slug = name.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def extract_from_menu(self, menu_data: dict, dispensary: str) -> List[Dict[str, str]]:
        """Extract product URLs from menu JSON."""
        products = []
        
        try:
            if dispensary == 'trulieve':
                # Trulieve stores batch data, not product pages - skip for now
                # Would need different scraping strategy (batch list page)
                pass
            
            elif dispensary == 'muv':
                # MUV: products is dict with 'list' key
                items = menu_data.get('products', {})
                if isinstance(items, dict) and 'list' in items:
                    items = items['list']
                    for item in items:
                        name = item.get('name', '')
                        slug = item.get('slug') or self.slugify(name)
                        if name:
                            url = self.DISPENSARY_URL_PATTERNS['muv'].format(slug=slug)
                            products.append({'strain_name': name, 'url': url})
            
            elif dispensary == 'cookies':
                # Cookies: products is dict with 'results' key, items have 'link' field
                items = menu_data.get('products', {})
                if isinstance(items, dict) and 'results' in items:
                    items = items['results']
                    for item in items:
                        name = item.get('name', '')
                        url = item.get('link', '')  # Use actual link from API
                        if name and url:
                            products.append({'strain_name': name, 'url': url})
            
            elif dispensary == 'curaleaf':
                # Curaleaf: products is list, items have 'detail_url' field
                items = menu_data.get('products', [])
                for item in items:
                    name = item.get('name', '')
                    url = item.get('detail_url', '')  # Use actual URL from API
                    if name and url:
                        products.append({'strain_name': name, 'url': url})
            
            elif dispensary == 'flowery':
                # Flowery: products is list, items have 'slug' field
                items = menu_data.get('products', [])
                for item in items:
                    name = item.get('name', '')
                    slug = item.get('slug', '')
                    if name and slug:
                        url = self.DISPENSARY_URL_PATTERNS['flowery'].format(slug=slug)
                        products.append({'strain_name': name, 'url': url})
        
        except Exception as e:
            print(f"Error extracting URLs from {dispensary}: {e}")
        
        return products
    
    def get_recent_menus(self, dispensary: str, days_back: int = 7) -> List[str]:
        """Get blob names for recent menu files."""
        container_client = self.blob_service.get_container_client(self.container)
        
        from datetime import timezone
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        prefix = f"dispensaries/{dispensary}/"
        
        blob_names = []
        for blob in container_client.list_blobs(name_starts_with=prefix):
            if blob.last_modified >= cutoff_date and blob.name.endswith('.json'):
                blob_names.append(blob.name)
        
        return blob_names
    
    def download_blob(self, blob_name: str) -> dict:
        """Download and parse JSON blob."""
        blob_client = self.blob_service.get_blob_client(self.container, blob_name)
        blob_data = blob_client.download_blob().readall()
        return json.loads(blob_data)
    
    def extract_all_urls(self, dispensary: str, max_files: int = 10) -> List[Dict[str, str]]:
        """Extract URLs from recent menu files for a dispensary."""
        print(f"\n Extracting product URLs from {dispensary}...")
        
        blob_names = self.get_recent_menus(dispensary, days_back=30)
        blob_names = blob_names[:max_files]  # Limit to avoid rate limiting
        
        all_products = []
        seen_names = set()
        
        for blob_name in blob_names:
            try:
                menu_data = self.download_blob(blob_name)
                products = self.extract_from_menu(menu_data, dispensary)
                
                # Deduplicate
                for p in products:
                    if p['strain_name'] not in seen_names:
                        all_products.append(p)
                        seen_names.add(p['strain_name'])
                
                print(f"   {blob_name}: {len(products)} products")
            except Exception as e:
                print(f"   {blob_name}: {e}")
        
        print(f"\n Total unique products from {dispensary}: {len(all_products)}")
        return all_products


if __name__ == "__main__":
    extractor = ProductURLExtractor()
    
    # Example: Extract URLs for Trulieve
    urls = extractor.extract_all_urls("trulieve", max_files=5)
    
    # Save to file for use with web scraper
    with open("trulieve_product_urls.json", "w") as f:
        json.dump(urls, f, indent=2)
    
    print(f"\n Saved {len(urls)} product URLs to trulieve_product_urls.json")
    print("Next: Use these URLs with genetics_webscraper.py")
