"""
MÜV Dispensary Download Module
Handles data collection from MÜV dispensary API
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Detect if running as package
_RUNNING_AS_PACKAGE = "terprint_menu_downloader" in __name__

class MuvDownloader:
    """MÜV dispensary data downloader"""
    
    def __init__(self, output_dir: str, store_ids: Optional[List[str]] = None, azure_manager=None):
        self.output_dir = output_dir
        self.azure_manager = azure_manager
        if store_ids is None:
            # Default to all known MÜV store IDs
            self.store_ids = [
                '298', '299', '300', '301', '302', '303', '304', '305', '306', '307',
                '308', '309', '310', '311', '312', '313', '314', '315', '316', '317',
                '318', '319', '320', '321', '322', '323', '324', '325', '326', '327',
                '328', '329', '330', '331', '332', '333', '334', '335', '336', '337',
                '338', '339', '340', '341', '342', '343', '344', '345', '346', '347',
                '348', '349', '350', '351', '352', '353', '354', '355', '356', '357',
                '358', '359', '360', '361', '362', '363', '364', '365', '366', '367',
                '368', '369', '370', '371', '372', '373', '374', '375', '376', '377',
                '378', '379', '380', '381', '382', '383'
            ]
        else:
            self.store_ids = store_ids
        self.dispensary_name = 'MÜV'
        
    def download(self) -> List[Tuple[str, Dict]]:
        """Download MÜV dispensary data"""
        print(f"Starting {self.dispensary_name} download...")
        
        try:
            # Import MÜV module - use package import when running as package
            if _RUNNING_AS_PACKAGE:
                from ..menus.muv import get_muv_products
            else:
                # Fallback for standalone testing
                try:
                    from terprint_menu_downloader.menus.muv import get_muv_products
                except ImportError:
                    from menus.muv import get_muv_products
            
            results = []
            
            def download_store(store_id):
                """Download data for a single store"""
                try:
                    print(f"   Downloading {self.dispensary_name} store {store_id}...")
                    
                    # Get products from API
                    products = get_muv_products(store_id)
                    
                    if products:
                        # Create filename with timestamp
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"muv_products_store_{store_id}_{timestamp}.json"
                        
                        # Add metadata
                        data_with_metadata = {
                            'timestamp': timestamp,
                            'dispensary': 'muv',
                            'store_id': store_id,
                            'download_time': datetime.now().isoformat(),
                            'product_count': len(products.get('data', [])) if isinstance(products.get('data'), list) else 0,
                            'raw_response_size': len(json.dumps(products)) if products else 0,
                            'downloader_version': '1.0',
                            'products': products
                        }
                        
                        # Save to Azure Data Lake if available
                        if self.azure_manager:
                            try:
                                # Create date-based folder structure
                                date_folder = datetime.now().strftime("%Y/%m/%d")
                                azure_path = f"dispensaries/muv/{date_folder}/{filename}"
                                
                                success = self.azure_manager.save_json_to_data_lake(
                                    json_data=data_with_metadata,
                                    file_path=azure_path,
                                    overwrite=True
                                )
                                
                                if success:
                                    # Return virtual filepath for tracking and the data
                                    filepath = f"azure://{azure_path}"
                                    file_size = len(json.dumps(data_with_metadata))
                                    print(f"   SUCCESS: {self.dispensary_name} store {store_id}: {data_with_metadata['product_count']} products saved to Azure ({file_size:,} bytes)")
                                    print(f"      Saved to: {azure_path}")
                                    return (filepath, data_with_metadata)
                                else:
                                    raise Exception(f"Failed to save to Azure Data Lake: {azure_path}")
                            except Exception as azure_error:
                                error_msg = f"{self.dispensary_name} store {store_id}: Failed to save to Azure: {azure_error}"
                                print(f"   ERROR: {error_msg}")
                                raise Exception(error_msg)
                        else:
                            error_msg = f"{self.dispensary_name} store {store_id}: Azure Data Lake Manager not available"
                            print(f"   ERROR: {error_msg}")
                            raise Exception(error_msg)
                        
                    else:
                        error_msg = f"{self.dispensary_name} store {store_id}: No data received from API"
                        print(f"   ERROR: {error_msg}")
                        raise Exception(error_msg)
                        
                except Exception as e:
                    # Log the per-store error but do NOT raise. We want the
                    # overall downloader to continue and return any successful
                    # store downloads so later upload logic can process them.
                    error_msg = f"{self.dispensary_name} store {store_id}: {str(e)}"
                    print(f"   ERROR: {error_msg}")
                    # Return None to indicate this store failed; the caller
                    # will skip None results and continue processing other
                    # stores.
                    return None
            
            # Process stores in parallel if there are multiple stores
            if len(self.store_ids) > 1:
                print(f"   Processing {len(self.store_ids)} stores in parallel...")
                with ThreadPoolExecutor(max_workers=min(5, len(self.store_ids))) as executor:
                    future_to_store = {executor.submit(download_store, store_id): store_id 
                                      for store_id in self.store_ids}
                    
                    for future in as_completed(future_to_store):
                        store_id = future_to_store[future]
                        try:
                            result = future.result()
                            if result:
                                results.append(result)
                            else:
                                print(f"   WARNING: {self.dispensary_name} store {store_id} failed and returned no result")
                        except Exception as e:
                            # Avoid failing the entire downloader if one store
                            # raised an exception at runtime — just record and
                            # continue so other stores still return their data.
                            print(f"   ERROR processing store {store_id}: {e}")
                            continue
            else:
                # Single store - no need for parallel processing
                for store_id in self.store_ids:
                    result = download_store(store_id)
                    if result:
                        results.append(result)
                    else:
                        print(f"   WARNING: {self.dispensary_name} store {store_id} failed and returned no result (continuing)")
            
            return results
            
        except ImportError as e:
            error_msg = f"Could not import {self.dispensary_name} module: {e}"
            print(f"ERROR: {error_msg}")
            print(f"   Check that menuMuv.py exists in: {os.path.join(grandparent_dir, 'menus')}")
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"{self.dispensary_name} download failed: {e}"
            print(f"ERROR: {error_msg}")
            raise Exception(error_msg)
    
    def get_config(self) -> Dict:
        """Get downloader configuration"""
        return {
            'name': self.dispensary_name,
            'store_ids': self.store_ids,
            'output_dir': self.output_dir,
            'enabled': True
        }
    
    def get_stock_status(self, batch_id: str, store_id: str = None, 
                         user_lat: float = None, user_lng: float = None,
                         max_distance: float = None) -> Dict:
        """
        Check real-time stock status for a batch ID across MÜV stores.
        
        Args:
            batch_id: Batch ID to check stock for
            store_id: Optional specific store to check
            user_lat: Optional user latitude for distance calculations
            user_lng: Optional user longitude for distance calculations
            max_distance: Optional maximum distance in miles
            
        Returns:
            Dict with stock status, stores carrying the product, and summary
        """
        from datetime import datetime
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
            # Import MÜV module for product lookup
            if _RUNNING_AS_PACKAGE:
                from ..menus.muv import get_muv_products
            else:
                try:
                    from terprint_menu_downloader.menus.muv import get_muv_products
                except ImportError:
                    from menus.muv import get_muv_products
            
            stores_to_check = [store_id] if store_id else self.store_ids
            in_stock_stores = []
            out_of_stock_stores = []
            product_name = None
            
            for sid in stores_to_check:
                try:
                    products_response = get_muv_products(sid)
                    products = products_response.get('data', []) if products_response else []
                    
                    # Search for batch_id in products
                    found = False
                    for product in products:
                        # Check batch codes in product
                        prod_batch = product.get('batch_id', '') or product.get('batchId', '')
                        if batch_id.lower() in str(prod_batch).lower():
                            found = True
                            if not product_name:
                                product_name = product.get('name', product.get('productName', 'Unknown'))
                            
                            store_info = {
                                'store_id': sid,
                                'store_name': f"MÜV Store {sid}",  # TODO: Add store name lookup
                                'in_stock': True,
                                'price': product.get('price', product.get('unitPrice')),
                                'quantity_available': product.get('quantity', product.get('availableQuantity')),
                                'location': {
                                    'address': None,  # TODO: Add store address lookup
                                    'lat': None,
                                    'lng': None
                                },
                                'distance_miles': None
                            }
                            
                            # Calculate distance if user location provided
                            if user_lat and user_lng and store_info['location']['lat']:
                                store_info['distance_miles'] = calculate_distance(
                                    user_lat, user_lng,
                                    store_info['location']['lat'], 
                                    store_info['location']['lng']
                                )
                                # Skip if beyond max_distance
                                if max_distance and store_info['distance_miles'] > max_distance:
                                    continue
                            
                            in_stock_stores.append(store_info)
                            break
                    
                    if not found:
                        out_of_stock_stores.append({'store_id': sid, 'in_stock': False})
                        
                except Exception as e:
                    print(f"Error checking store {sid}: {e}")
                    continue
            
            # Sort by distance if available
            if user_lat and user_lng:
                in_stock_stores.sort(key=lambda s: s.get('distance_miles') or float('inf'))
            
            return {
                'batch_id': batch_id,
                'dispensary': 'muv',
                'product_name': product_name,
                'checked_at': datetime.utcnow().isoformat(),
                'status': 'in_stock' if in_stock_stores else 'out_of_stock',
                'stores': in_stock_stores,
                'summary': {
                    'total_stores_checked': len(stores_to_check),
                    'in_stock_count': len(in_stock_stores),
                    'out_of_stock_count': len(out_of_stock_stores),
                    'nearest_in_stock': in_stock_stores[0] if in_stock_stores else None
                }
            }
            
        except Exception as e:
            return {
                'batch_id': batch_id,
                'dispensary': 'muv',
                'product_name': None,
                'checked_at': datetime.utcnow().isoformat(),
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