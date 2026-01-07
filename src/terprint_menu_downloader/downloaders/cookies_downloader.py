"""
Cookies Florida Downloader Module
Downloads menu data from all Cookies Florida locations
"""
import json
import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class CookiesDownloader:
    """Download menu data from Cookies Florida dispensaries"""
    
    def __init__(self, output_dir: str = "downloads", azure_manager=None):
        self.output_dir = output_dir
        self.azure_manager = azure_manager
        
        # API endpoint template
        self.api_template = "https://cookiesflorida.co/wp-json/dovetail-api/v1/products?page=1&perpage=50&orderby=menu_setting&order=asc&retailer={slug}&menutype=medical&categories%5B%5D=premium-flower"
        
        # All Cookies Florida location slugs
        self.location_slugs = [
            "bradenton", "brooksville", "deland-woodland", "fort-myers",
            "gainesville", "jacksonville", "miami", "n-miami-beach",
            "orange-blossom", "orange-park", "orlando", "palm-bay",
            "pensacola", "port-charlotte", "port-st-lucie", "sanford",
            "tampa", "tampa-fletcher"
        ]
    
    def download_location(self, location_slug: str) -> Optional[Dict]:
        """Download menu data for a specific location"""
        try:
            api_url = self.api_template.format(slug=location_slug)
            response = requests.get(api_url, timeout=30)
            response.raise_for_status()
            
            menu_data = response.json()
            
            # Extract product count from API response
            if isinstance(menu_data, dict) and 'results' in menu_data:
                product_count = len(menu_data.get('results', []))
            elif isinstance(menu_data, list):
                product_count = len(menu_data)
            else:
                product_count = 0
            
            result = {
                "location": location_slug,
                "download_timestamp": datetime.now().isoformat(),
                "api_url": api_url,
                "product_count": product_count,
                "products": menu_data
            }
            
            return result
            
        except Exception as e:
            print(f"Error downloading {location_slug}: {e}")
            return None
    
    def download_all(self) -> Dict[str, List]:
        """Download menu data from all Cookies Florida locations"""
        print(f"\n{'='*60}")
        print(f"COOKIES FLORIDA - Starting download from {len(self.location_slugs)} locations")
        print(f"{'='*60}\n")
        
        results = []
        successful = 0
        failed = 0
        
        for location_slug in self.location_slugs:
            print(f"Downloading {location_slug}...", end=" ")
            
            result = self.download_location(location_slug)
            
            if result:
                # Save individual location file
                filename = f"cookies_{location_slug}_menu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(self.cookies_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                print(f"✓ {result['product_count']} products")
                results.append(result)
                successful += 1
            else:
                print(f"✗ Failed")
                failed += 1
            
            # Be nice to the server
            time.sleep(1)
        
        # Save combined results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_file = os.path.join(self.output_dir, f"cookies_downloads_{timestamp}.json")
        
        combined_data = {
            "download_timestamp": datetime.now().isoformat(),
            "total_locations": len(self.location_slugs),
            "successful_downloads": successful,
            "failed_downloads": failed,
            "locations": results
        }
        
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"COOKIES FLORIDA - Download Complete")
        print(f"Successful: {successful}/{len(self.location_slugs)}")
        print(f"Failed: {failed}")
        print(f"Combined file: {combined_file}")
        print(f"{'='*60}\n")
        
        return {
            'cookies': results
        }
    
    def download(self) -> List:
        """Download method called by orchestrator - returns list of tuples (filename, data)"""
        print(f"\n{'='*60}")
        print(f"COOKIES FLORIDA - Starting download from {len(self.location_slugs)} locations")
        print(f"{'='*60}\n")
        
        results = []
        
        for location_slug in self.location_slugs:
            print(f"   Downloading {location_slug}...", end=" ")
            
            result = self.download_location(location_slug)
            
            if result:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"cookies_{location_slug}_menu_{timestamp}.json"
                
                # Save to Azure Data Lake if available
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        azure_path = f"dispensaries/cookies/{date_folder}/{filename}"
                        
                        success = self.azure_manager.save_json_to_data_lake(
                            json_data=result,
                            file_path=azure_path,
                            overwrite=True
                        )
                        
                        if success:
                            filepath = f"azure://{azure_path}"
                            print(f"✓ {result['product_count']} products saved to Azure")
                            results.append((filepath, result))
                        else:
                            print(f"✗ Failed to save to Azure")
                    except Exception as azure_error:
                        print(f"✗ Azure save error: {azure_error}")
                else:
                    print(f"✗ Azure Data Lake Manager not available")
            else:
                print(f"✗ Failed to download")
            
            # Be nice to the server
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"COOKIES FLORIDA - Download Complete")
        print(f"Total files saved to Azure: {len(results)}")
        print(f"{'='*60}\n")
        
        return results
    
    def get_latest_download(self) -> Optional[str]:
        """Get the path to the most recent combined download file"""
        downloads = [f for f in os.listdir(self.output_dir) 
                    if f.startswith('cookies_downloads_') and f.endswith('.json')]
        
        if not downloads:
            return None
        
        downloads.sort(reverse=True)
        return os.path.join(self.output_dir, downloads[0])
    
    def get_stock_status(self, batch_id: str, store_id: str = None, 
                         user_lat: float = None, user_lng: float = None,
                         max_distance: float = None) -> Dict:
        """
        Check real-time stock status for a batch ID across Cookies stores.
        
        Args:
            batch_id: Batch ID to check stock for
            store_id: Optional specific store slug to check
            user_lat: Optional user latitude for distance calculations
            user_lng: Optional user longitude for distance calculations
            max_distance: Optional maximum distance in miles
            
        Returns:
            Dict with stock status, stores carrying the product, and summary
        """
        import math
        
        def calculate_distance(lat1, lng1, lat2, lng2):
            """Calculate distance in miles between two coordinates"""
            R = 3959  # Earth's radius in miles
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            dlat = math.radians(lat2 - lat1)
            dlng = math.radians(lng2 - lng1)
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        try:
            locations_to_check = [store_id] if store_id else self.location_slugs
            in_stock_stores = []
            out_of_stock_stores = []
            product_name = None
            
            for slug in locations_to_check:
                try:
                    result = self.download_location(slug)
                    if not result:
                        out_of_stock_stores.append({'store_id': slug, 'in_stock': False})
                        continue
                    
                    products = result.get('products', {})
                    # Handle both list and dict responses
                    if isinstance(products, dict):
                        products = products.get('results', [])
                    
                    # Search for batch_id in products
                    found = False
                    for product in products:
                        prod_batch = str(product.get('batch_id', '') or product.get('batch', '') or '')
                        prod_sku = str(product.get('sku', '') or '')
                        
                        if batch_id.lower() in prod_batch.lower() or batch_id.lower() in prod_sku.lower():
                            found = True
                            if not product_name:
                                product_name = product.get('name', product.get('title', 'Unknown'))
                            
                            store_info = {
                                'store_id': slug,
                                'store_name': f"Cookies {slug.replace('-', ' ').title()}",
                                'in_stock': True,
                                'price': product.get('price'),
                                'quantity_available': product.get('quantity'),
                                'location': {
                                    'address': None,
                                    'lat': None,
                                    'lng': None
                                },
                                'distance_miles': None
                            }
                            
                            # Calculate distance if available
                            if user_lat and user_lng and store_info['location']['lat']:
                                store_info['distance_miles'] = calculate_distance(
                                    user_lat, user_lng,
                                    store_info['location']['lat'], 
                                    store_info['location']['lng']
                                )
                                if max_distance and store_info['distance_miles'] > max_distance:
                                    continue
                            
                            in_stock_stores.append(store_info)
                            break
                    
                    if not found:
                        out_of_stock_stores.append({'store_id': slug, 'in_stock': False})
                        
                except Exception as e:
                    print(f"Error checking store {slug}: {e}")
                    continue
                
                # Rate limit
                time.sleep(0.5)
            
            # Sort by distance if available
            if user_lat and user_lng:
                in_stock_stores.sort(key=lambda s: s.get('distance_miles') or float('inf'))
            
            return {
                'batch_id': batch_id,
                'dispensary': 'cookies',
                'product_name': product_name,
                'checked_at': datetime.now().isoformat(),
                'status': 'in_stock' if in_stock_stores else 'out_of_stock',
                'stores': in_stock_stores,
                'summary': {
                    'total_stores_checked': len(locations_to_check),
                    'in_stock_count': len(in_stock_stores),
                    'out_of_stock_count': len(out_of_stock_stores),
                    'nearest_in_stock': in_stock_stores[0] if in_stock_stores else None
                }
            }
            
        except Exception as e:
            return {
                'batch_id': batch_id,
                'dispensary': 'cookies',
                'product_name': None,
                'checked_at': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e),
                'stores': [],
                'summary': {
                    'total_stores_checked': 0,
                    'in_stock_count': 0,
                    'out_of_stock_count': 0,
                    'nearest_in_stock': None
                }
            }
