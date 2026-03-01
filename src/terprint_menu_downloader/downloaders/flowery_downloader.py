"""
The Flowery Downloader Module
Downloads menu data from all The Flowery locations using Bearer token authentication
"""
import json
import os
import requests
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Selenium is optional - only needed for token extraction
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    Options = None


class FloweryDownloader:
    """Download menu data from The Flowery dispensaries"""
    
    def __init__(self, output_dir: str = "downloads", azure_manager=None, location_ids=None):
        self.output_dir = output_dir
        self.azure_manager = azure_manager
        self.location_ids = location_ids  # Optional list of specific location IDs to download
        self.flowery_dir = os.path.join(output_dir, "flowery") if output_dir else None
        
        # API endpoints
        self.locations_api = "https://api.theflowery.co/wp-json/salve/v1/data/locations"
        self.products_api = "https://app.getsalve.co/api/products"
        
        # Bearer token (will be extracted from Selenium session)
        self.bearer_token = None
        
        # Locations data
        self.locations = []
    
    def _extract_bearer_token(self) -> Optional[str]:
        """Extract Bearer token from Selenium session by loading the website"""
        try:
            print("Extracting Bearer token from The Flowery website...")
            
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                # Load the shop page
                driver.get("https://theflowery.co/shop")
                time.sleep(3)  # Wait for API calls
                
                # Get performance logs
                logs = driver.get_log('performance')
                
                # Extract Bearer token from network requests
                for log in logs:
                    try:
                        message = json.loads(log['message'])
                        method = message.get('message', {}).get('method')
                        
                        if method == 'Network.requestWillBeSent':
                            request = message['message']['params']['request']
                            url = request.get('url', '')
                            headers = request.get('headers', {})
                            
                            # Look for products API calls with Authorization header
                            if 'app.getsalve.co/api/products' in url:
                                auth_header = headers.get('Authorization', '')
                                if auth_header.startswith('Bearer '):
                                    token = auth_header.replace('Bearer ', '')
                                    print(f"✓ Bearer token extracted (length: {len(token)})")
                                    return token
                    except:
                        continue
                
                print("✗ Could not find Bearer token in network logs")
                return None
                
            finally:
                driver.quit()
                
        except Exception as e:
            print(f"Error extracting Bearer token: {e}")
            return None
    
    def _load_bearer_token(self) -> bool:
        """Load or extract Bearer token"""
        # First try environment variable (for Azure Functions)
        env_token = os.environ.get('FLOWERY_BEARER_TOKEN')
        if env_token:
            self.bearer_token = env_token.strip()
            print(f"✓ Loaded Bearer token from environment variable (length: {len(self.bearer_token)})")
            return True
        
        # Try to load from saved file
        token_file = os.path.join(self.flowery_dir, "bearer_token.txt")
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    self.bearer_token = f.read().strip()
                print(f"✓ Loaded Bearer token from file (length: {len(self.bearer_token)})")
                return True
            except:
                pass
        
        # Extract fresh token (requires Selenium)
        if not SELENIUM_AVAILABLE:
            print("⚠️ Selenium not available - cannot extract fresh token. Set FLOWERY_BEARER_TOKEN environment variable.")
            return False
            
        self.bearer_token = self._extract_bearer_token()
        if self.bearer_token:
            # Save for future use
            try:
                with open(token_file, 'w') as f:
                    f.write(self.bearer_token)
                print(f"✓ Bearer token saved to {token_file}")
            except:
                pass
            return True
        
        return False
    
    def _fetch_locations(self) -> bool:
        """Fetch all location data from The Flowery locations API"""
        try:
            print("Fetching locations from The Flowery API...")
            response = requests.get(self.locations_api, timeout=30)
            response.raise_for_status()
            
            locations_data = response.json()
            
            # Handle response - API returns list directly or dict with 'locations' key
            if isinstance(locations_data, list):
                self.locations = locations_data
            elif isinstance(locations_data, dict) and 'locations' in locations_data:
                self.locations = locations_data.get('locations', [])
            else:
                self.locations = []
            
            if self.locations:
                print(f"✓ Found {len(self.locations)} locations")
                return True
            else:
                print("✗ No locations found")
                return False
                
        except Exception as e:
            print(f"Error fetching locations: {e}")
            return False
    
    def download_location(self, location_id: int, location_name: str) -> Optional[Dict]:
        """Download menu data for a specific location with pagination support"""
        try:
            if not self.bearer_token:
                print("No Bearer token available")
                return None
            
            headers = {
                'Authorization': f'Bearer {self.bearer_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            all_products = []
            current_page = 1
            total_pages = 1
            
            # Fetch all pages
            while current_page <= total_pages:
                api_url = f"{self.products_api}?location_id={location_id}&page={current_page}"
                response = requests.get(api_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                response_data = response.json()
                
                # Handle paginated response
                if isinstance(response_data, dict) and 'data' in response_data:
                    products = response_data['data']
                    all_products.extend(products)
                    
                    meta = response_data.get('meta', {})
                    total_pages = meta.get('last_page', 1)
                    current_page += 1
                elif isinstance(response_data, list):
                    all_products.extend(response_data)
                    break  # No pagination
                else:
                    break
                
                time.sleep(0.2)  # Rate limiting between pages
            
            # Filter out edibles — Terprint only processes flower, concentrates, and vapes
            filtered_products = [
                p for p in all_products
                if not any("edible" in str(cat).lower() for cat in (p.get("categories") or [p.get("category", "")]))
            ]
            edibles_filtered = len(all_products) - len(filtered_products)
            if edibles_filtered:
                print(f"  (filtered out {edibles_filtered} edibles product(s))")

            result = {
                "location_id": location_id,
                "location": location_name,
                "download_timestamp": datetime.now().isoformat(),
                "api_url": f"{self.products_api}?location_id={location_id}",
                "total_products": len(filtered_products),
                "product_count": len(filtered_products),
                "products": filtered_products
            }
            
            return result
            
        except Exception as e:
            print(f"Error downloading location {location_name}: {e}")
            return None
    
    def download(self) -> List[Tuple[str, Dict]]:
        """
        Download menu data from all The Flowery locations
        Returns list of (filepath, data) tuples for orchestrator compatibility
        """
        print(f"\n{'='*60}")
        print(f"THE FLOWERY - Starting download")
        print(f"{'='*60}\n")
        
        # Load Bearer token
        if not self._load_bearer_token():
            print("✗ Failed to obtain Bearer token")
            return []
        
        # Fetch locations
        if not self._fetch_locations():
            print("✗ Failed to fetch locations")
            return []
        
        print(f"\nDownloading from {len(self.locations)} locations...\n")
        
        results = []
        successful = 0
        failed = 0
        total_products = 0
        
        for location in self.locations:
            location_id = location.get('id')
            location_name = location.get('name', f'Location_{location_id}')
            
            print(f"   Downloading {location_name} (ID: {location_id})...", end=" ")
            
            result = self.download_location(location_id, location_name)
            
            if result:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"flowery_{location_name.lower().replace(' ', '_')}_menu_{timestamp}.json"
                
                # Save to Azure Data Lake if available
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        azure_path = f"dispensaries/flowery/{date_folder}/{filename}"
                        
                        success = self.azure_manager.save_json_to_data_lake(
                            json_data=result,
                            file_path=azure_path,
                            overwrite=True
                        )
                        
                        if success:
                            filepath = f"azure://{azure_path}"
                            print(f"SUCCESS: {result['product_count']} products saved to Azure")
                            results.append((filepath, result))
                            successful += 1
                            total_products += result['total_products']
                        else:
                            print(f"ERROR: Failed to save to Azure")
                            failed += 1
                    except Exception as azure_error:
                        print(f"ERROR: Azure save error: {azure_error}")
                        failed += 1
                else:
                    print(f"ERROR: Azure Data Lake Manager not available")
                    failed += 1
            else:
                print(f"ERROR: Failed to download")
                failed += 1
            
            # Be nice to the server
            time.sleep(1)
        
        print(f"\n{'='*60}")
        print(f"THE FLOWERY - Download Complete")
        print(f"{'='*60}")
        print(f"   SUCCESS: {successful}/{len(self.locations)} locations")
        print(f"   Total products: {total_products}")
        print(f"   Total files saved to Azure: {len(results)}")
        print(f"{'='*60}\n")
        
        return results
    
    def download_all(self) -> Dict[str, List]:
        """Download menu data from all The Flowery locations"""
        print(f"\n{'='*60}")
        print(f"THE FLOWERY - Starting download")
        print(f"{'='*60}\n")
        
        # Load Bearer token
        if not self._load_bearer_token():
            print("✗ Failed to obtain Bearer token")
            return {
                'successful': [],
                'failed': [],
                'summary': {
                    'successful': 0,
                    'failed': 0,
                    'total_locations': 0,
                    'total_products': 0
                }
            }
        
        # Fetch locations
        if not self._fetch_locations():
            print("✗ Failed to fetch locations")
            return {
                'successful': [],
                'failed': [],
                'summary': {
                    'successful': 0,
                    'failed': 0,
                    'total_locations': 0,
                    'total_products': 0
                }
            }
        
        print(f"\nDownloading from {len(self.locations)} locations...\n")
        
        results = []
        successful = 0
        failed = 0
        total_products = 0
        
        for location in self.locations:
            location_id = location.get('id')
            location_name = location.get('name', f'Location_{location_id}')
            
            print(f"Downloading {location_name} (ID: {location_id})...", end=" ")
            
            result = self.download_location(location_id, location_name)
            
            if result:
                # Save individual location file
                filename = f"flowery_{location_name.lower().replace(' ', '_')}_menu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(self.flowery_dir, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                
                print(f"✓ {result['product_count']} products")
                results.append(result)
                successful += 1
                total_products += result['total_products']
            else:
                print(f"✗ Failed")
                failed += 1
            
            # Be nice to the server
            time.sleep(1)
        
        # Save combined results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        combined_file = os.path.join(self.output_dir, f"flowery_downloads_{timestamp}.json")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'locations': results,
            'summary': {
                'successful': successful,
                'failed': failed,
                'total_locations': len(self.locations),
                'total_products': total_products
            }
        }
        
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print(f"THE FLOWERY - Download Complete")
        print(f"{'='*60}")
        print(f"Successful: {successful}/{len(self.locations)} locations")
        print(f"Total products: {total_products}")
        print(f"Combined results: {combined_file}")
        print(f"{'='*60}\n")
        
        return {
            'successful': [r for r in results if r],
            'failed': [loc for loc in self.locations if loc.get('id') not in [r['location_id'] for r in results]],
            'summary': summary['summary']
        }


if __name__ == "__main__":
    # Test download
    downloader = FloweryDownloader()
    results = downloader.download_all()
    print(json.dumps(results['summary'], indent=2))


# Add get_stock_status method to FloweryDownloader class
# This is added after the class definition to avoid indentation issues
def _flowery_get_stock_status(self, batch_id: str, store_id: str = None, 
                               user_lat: float = None, user_lng: float = None,
                               max_distance: float = None) -> Dict:
    """
    Check real-time stock status for a batch ID across Flowery stores.
    
    Args:
        batch_id: Batch ID to check stock for
        store_id: Optional specific store ID to check
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
        # Load bearer token and locations
        if not self.bearer_token:
            if not self._load_bearer_token():
                raise Exception("Could not load Flowery bearer token")
        
        if not self.locations:
            self._fetch_locations()
        
        locations_to_check = self.locations
        if store_id:
            locations_to_check = [loc for loc in self.locations if str(loc.get('id')) == str(store_id)]
        
        in_stock_stores = []
        out_of_stock_stores = []
        product_name = None
        
        for location in locations_to_check:
            try:
                location_id = location.get('id')
                location_name = location.get('name', f'Location_{location_id}')
                
                result = self.download_location(location_id, location_name)
                if not result:
                    out_of_stock_stores.append({'store_id': str(location_id), 'in_stock': False})
                    continue
                
                products = result.get('products', [])
                
                # Search for batch_id in products
                found = False
                for product in products:
                    prod_batch = str(product.get('batch_id', '') or product.get('batchNumber', '') or '')
                    prod_sku = str(product.get('sku', '') or product.get('productSku', '') or '')
                    
                    if batch_id.lower() in prod_batch.lower() or batch_id.lower() in prod_sku.lower():
                        found = True
                        if not product_name:
                            product_name = product.get('name', product.get('productName', 'Unknown'))
                        
                        # Get location coordinates
                        loc_lat = location.get('latitude') or location.get('lat')
                        loc_lng = location.get('longitude') or location.get('lng') or location.get('lon')
                        
                        store_info = {
                            'store_id': str(location_id),
                            'store_name': f"The Flowery - {location_name}",
                            'in_stock': True,
                            'price': product.get('price'),
                            'quantity_available': product.get('quantity'),
                            'location': {
                                'address': location.get('address'),
                                'lat': float(loc_lat) if loc_lat else None,
                                'lng': float(loc_lng) if loc_lng else None
                            },
                            'distance_miles': None
                        }
                        
                        # Calculate distance if available
                        if user_lat and user_lng and store_info['location']['lat'] and store_info['location']['lng']:
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
                    out_of_stock_stores.append({'store_id': str(location_id), 'in_stock': False})
                    
            except Exception as e:
                print(f"Error checking location {location.get('id')}: {e}")
                continue
            
            # Rate limit
            time.sleep(0.3)
        
        # Sort by distance if available
        if user_lat and user_lng:
            in_stock_stores.sort(key=lambda s: s.get('distance_miles') or float('inf'))
        
        return {
            'batch_id': batch_id,
            'dispensary': 'flowery',
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
            'dispensary': 'flowery',
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


# Attach the method to the class
FloweryDownloader.get_stock_status = _flowery_get_stock_status
