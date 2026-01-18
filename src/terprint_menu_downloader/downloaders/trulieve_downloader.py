"""
Trulieve Dispensary Download Module
Handles data collection from Trulieve dispensary API
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple

# Detect if running as package
_RUNNING_AS_PACKAGE = "terprint_menu_downloader" in __name__

class TrulieveDownloader:
    """Trulieve dispensary data downloader"""
    
    def __init__(self, output_dir: str, dev_mode: bool = False, store_ids: List[str] = None, category_ids: List[str] = None, azure_manager=None):
        self.output_dir = output_dir
        self.dispensary_name = 'Trulieve'
        self.dev_mode = dev_mode
        self.store_ids = store_ids
        self.category_ids = category_ids
        self.azure_manager = azure_manager
    
    @staticmethod
    def _extract_batch_codes(products: List[Dict], category_id: str = '') -> List[str]:
        """Return sorted unique SKU_BATCH|CATEGORYID combinations from products"""
        batch_codes = set()
        for product in products or []:
            sku = product.get('sku', '')
            if not sku:
                continue
            for option in product.get('configurable_options', []) or []:
                if option.get('attribute_code') != 'batch_codes':
                    continue
                for value in option.get('values', []) or []:
                    label = value.get('label')
                    if label:
                        batch_code = f"{sku}_{str(label).strip()}|{category_id}"
                        batch_codes.add(batch_code)
        return sorted(batch_codes)
    
    @staticmethod
    def _write_batch_list_file(filepath: str, batch_codes: List[str]):
        """Prepare batch list data structure (returns deduped codes for Azure save)"""
        # Deduplicate and maintain sort order
        unique_codes = sorted(set(batch_codes))
        return unique_codes
        
    def download(self) -> List[Tuple[str, Dict]]:
        """Download Trulieve dispensary data and split into separate files by store and category"""
        mode_name = "DEVELOPMENT" if self.dev_mode else "PRODUCTION"
        print(f"Starting {self.dispensary_name} download ({mode_name} mode)...")
        
        try:
            # Import the working collection function using package-aware imports
            print(f"   Importing trulieve_fixed.collect_all_trulieve_data_browser_format...")
            if _RUNNING_AS_PACKAGE:
                from ..menus.trulieve_fixed import collect_all_trulieve_data_browser_format
            else:
                # Fallback for standalone testing
                try:
                    from terprint_menu_downloader.menus.trulieve_fixed import collect_all_trulieve_data_browser_format
                except ImportError:
                    from menus.trulieve_fixed import collect_all_trulieve_data_browser_format
            print(f"   ✓ Import successful")
            
            results = []
            
            # Call ONLY the working function with dev_mode parameter
            print(f"   Calling collect_all_trulieve_data_browser_format(dev_mode={self.dev_mode}, store_ids={self.store_ids}, category_ids={self.category_ids})...")
            all_data = collect_all_trulieve_data_browser_format(dev_mode=self.dev_mode, store_ids=self.store_ids, category_ids=self.category_ids)
            print(f"   ✓ Function call completed")
            
            # Check if we got valid data
            if not all_data:
                raise Exception("collect_all_trulieve_data_browser_format returned None")
            
            if not isinstance(all_data, dict):
                raise Exception(f"Expected dict, got {type(all_data)}")
            
            summary = all_data.get('summary', {})
            total_products = summary.get('total_products', 0)
            
            print(f"   ✓ Received data with {total_products} total products")
            
            if total_products > 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Create separate files for each store/category combination
                stores_data = all_data.get('stores', {})
                print(f"   Creating separate files for {len(stores_data)} store/category combinations...")
                combined_batch_codes = set()
                
                for config, store_data in stores_data.items():
                    if not store_data.get('success', False):
                        continue
                    
                    store_id = store_data.get('store_id', 'unknown')
                    category_id = store_data.get('category_id', 'unknown')
                    products = store_data.get('products', [])
                    
                    if not products:
                        continue
                    
                    # Create filename: trulieve_products_store-{name}_cat-{id}_{timestamp}.json
                    filename = f"trulieve_products_store-{store_id}_cat-{category_id}_{timestamp}.json"
                    
                    # Create file data structure
                    file_data = {
                        'timestamp': timestamp,
                        'dispensary': 'trulieve',
                        'store_id': store_id,
                        'category_id': category_id,
                        'config': config,
                        'download_time': datetime.now().isoformat(),
                        'downloader_version': '1.0',
                        'download_method': 'menuTrulieveFixed_browser_format',
                        'products_count': len(products),
                        'total_available': store_data.get('total_available', len(products)),
                        'products': products
                    }
                    batch_codes = self._extract_batch_codes(products, category_id)
                    if batch_codes:
                        unique_batch_codes = self._write_batch_list_file('', batch_codes)
                        file_data['batch_codes'] = unique_batch_codes
                        file_data['batch_list_count'] = len(unique_batch_codes)
                        combined_batch_codes.update(unique_batch_codes)
                        print(f"      ✓ {config}: captured {len(unique_batch_codes)} batch codes")
                    
                    # Save to Azure Data Lake if available
                    if self.azure_manager:
                        try:
                            date_folder = datetime.now().strftime("%Y/%m/%d")
                            azure_path = f"dispensaries/trulieve/{date_folder}/{filename}"
                            
                            success = self.azure_manager.save_json_to_data_lake(
                                json_data=file_data,
                                file_path=azure_path,
                                overwrite=True
                            )
                            
                            if success:
                                filepath = f"azure://{azure_path}"
                                file_size = len(json.dumps(file_data))
                                print(f"      ✓ {config}: {len(products)} products saved to Azure ({file_size:,} bytes)")
                                results.append((filepath, file_data))
                            else:
                                print(f"      ✗ {config}: Failed to save to Azure")
                        except Exception as azure_error:
                            print(f"      ✗ {config}: Azure save error: {azure_error}")
                    else:
                        print(f"      ✗ {config}: Azure Data Lake Manager not available")
                
                # Also create a summary file with metadata
                summary_filename = f"trulieve_products_summary_{timestamp}.json"
                
                summary_data = {
                    'timestamp': timestamp,
                    'dispensary': 'trulieve',
                    'download_time': datetime.now().isoformat(),
                    'downloader_version': '1.0',
                    'download_method': 'menuTrulieveFixed_browser_format',
                    'total_products': total_products,
                    'successful_stores': summary.get('successful_stores', 0),
                    'failed_stores': summary.get('failed_stores', 0),
                    'working_configurations': summary.get('working_configurations', []),
                    'failed_configurations': summary.get('failed_configurations', []),
                    'files_created': len(results),
                    'collection_timestamp': all_data.get('collection_timestamp')
                }
                combined_batch_list = sorted(combined_batch_codes)
                summary_data['batch_list_count'] = len(combined_batch_list)
                
                # Add combined batch list as uploadable result with batch list data
                batch_list_data = {
                    'timestamp': timestamp,
                    'dispensary': 'trulieve',
                    'download_time': datetime.now().isoformat(),
                    'type': 'batch_list',
                    'batch_count': len(combined_batch_list),
                    'batches': combined_batch_list
                }
                
                # Save summary and batch list to Azure
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        
                        # Save summary
                        summary_azure_path = f"dispensaries/trulieve/{date_folder}/{summary_filename}"
                        summary_success = self.azure_manager.save_json_to_data_lake(
                            json_data=summary_data,
                            file_path=summary_azure_path,
                            overwrite=True
                        )
                        if summary_success:
                            print(f"   ✓ Summary saved to Azure: {summary_filename}")
                            results.append((f"azure://{summary_azure_path}", summary_data))
                        
                        # Save batch list
                        batch_list_filename = f"trulieve_batch_list_{timestamp}.json"
                        batch_list_azure_path = f"dispensaries/trulieve/{date_folder}/{batch_list_filename}"
                        batch_success = self.azure_manager.save_json_to_data_lake(
                            json_data=batch_list_data,
                            file_path=batch_list_azure_path,
                            overwrite=True
                        )
                        if batch_success:
                            print(f"   ✓ Combined batch list saved to Azure: {batch_list_filename} ({len(combined_batch_list)} unique codes)")
                            results.append((f"azure://{batch_list_azure_path}", batch_list_data))
                    except Exception as azure_error:
                        print(f"   ✗ Error saving summary/batch list to Azure: {azure_error}")
                
                print(f"   SUCCESS: {self.dispensary_name}: {len(results)} files saved to Azure")
                print(f"      Total products: {total_products} from {summary.get('successful_stores', 0)} store/category combinations")
                
                return results
                
            else:
                # No products collected
                error_msg = f"No products collected (successful_stores: {summary.get('successful_stores', 0)}, failed_stores: {summary.get('failed_stores', 0)})"
                failed_configs = summary.get('failed_configurations', [])
                if failed_configs:
                    error_msg += f", first few failed: {failed_configs[:3]}"
                
                print(f"   ERROR: {error_msg}")
                raise Exception(error_msg)
            
        except ImportError as e:
            error_msg = f"Could not import menuTrulieveFixed: {e}"
            print(f"ERROR: {error_msg}")
            
            # List available files for debugging
            trulieve_dir = os.path.join(grandparent_dir, "menus", "trulieve")
            if os.path.exists(trulieve_dir):
                files = [f for f in os.listdir(trulieve_dir) if f.endswith('.py')]
                print(f"   Available Python files in trulieve dir: {files}")
            
            raise ImportError(error_msg)
        
        except Exception as e:
            error_msg = f"{self.dispensary_name} download failed: {e}"
            print(f"ERROR: {error_msg}")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Error details: {str(e)}")
            raise Exception(error_msg)
    
    def get_config(self) -> Dict:
        """Get downloader configuration"""
        return {
            'name': self.dispensary_name,
            'output_dir': self.output_dir,
            'enabled': True,
            'method': 'menuTrulieveFixed_browser_format_only'
        }

    def test_download(self) -> bool:
        """Test if the Trulieve download function is available"""
        try:
            print(f"Testing {self.dispensary_name} function availability...")
            
            # Test import only
            from menuTrulieveFixed import collect_all_trulieve_data_browser_format
            print(f"   ✓ Successfully imported collect_all_trulieve_data_browser_format")
            
            # Check if it's callable
            if callable(collect_all_trulieve_data_browser_format):
                print(f"   ✓ Function is callable")
                return True
            else:
                print(f"   ✗ Function is not callable")
                return False
            
        except ImportError as e:
            print(f"   ✗ Import failed: {e}")
            return False
        except Exception as e:
            print(f"   ✗ Test failed: {e}")
            return False
    
    def get_stock_status(self, batch_id: str, store_id: str = None, 
                         user_lat: float = None, user_lng: float = None,
                         max_distance: float = None) -> Dict:
        """
        Check real-time stock status for a batch ID across Trulieve stores.
        
        Args:
            batch_id: Batch ID to check stock for (format: SKU_BATCHCODE)
            store_id: Optional specific store slug to check
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
            # Import Trulieve module
            if _RUNNING_AS_PACKAGE:
                from ..menus.trulieve_fixed import collect_all_trulieve_data_browser_format
            else:
                try:
                    from terprint_menu_downloader.menus.trulieve_fixed import collect_all_trulieve_data_browser_format
                except ImportError:
                    from menus.trulieve_fixed import collect_all_trulieve_data_browser_format
            
            # Parse batch_id (format: SKU_BATCHCODE|CATEGORYID)
            search_batch = batch_id.split('|')[0] if '|' in batch_id else batch_id
            
            # If store_id specified, only check that store
            stores_to_check = [store_id] if store_id else self.store_ids
            
            in_stock_stores = []
            out_of_stock_stores = []
            product_name = None
            
            # Collect data - use instance dev_mode setting
            all_data = collect_all_trulieve_data_browser_format(
                dev_mode=self.dev_mode,  # Use instance setting, not hardcoded True
                store_ids=stores_to_check
            )
            
            if all_data and 'stores' in all_data:
                for config, store_data in all_data['stores'].items():
                    if not store_data.get('success', False):
                        continue
                    
                    sid = store_data.get('store_id', 'unknown')
                    products = store_data.get('products', [])
                    
                    # Search for batch_id in products
                    for product in products:
                        batch_codes = self._extract_batch_codes([product], store_data.get('category_id', ''))
                        
                        for bc in batch_codes:
                            if search_batch.lower() in bc.lower():
                                if not product_name:
                                    product_name = product.get('name', 'Unknown')
                                
                                store_info = {
                                    'store_id': sid,
                                    'store_name': f"Trulieve {sid.replace('_', ' ').title()}",
                                    'in_stock': True,
                                    'price': product.get('price', {}).get('regularPrice', {}).get('amount'),
                                    'quantity_available': None,  # Trulieve doesn't expose quantity
                                    'category_id': store_data.get('category_id'),
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
            
            # Sort by distance if available
            if user_lat and user_lng:
                in_stock_stores.sort(key=lambda s: s.get('distance_miles') or float('inf'))
            
            return {
                'batch_id': batch_id,
                'dispensary': 'trulieve',
                'product_name': product_name,
                'checked_at': datetime.utcnow().isoformat(),
                'status': 'in_stock' if in_stock_stores else 'out_of_stock',
                'stores': in_stock_stores,
                'summary': {
                    'total_stores_checked': len(stores_to_check) if stores_to_check else 0,
                    'in_stock_count': len(in_stock_stores),
                    'out_of_stock_count': len(out_of_stock_stores),
                    'nearest_in_stock': in_stock_stores[0] if in_stock_stores else None
                }
            }
            
        except Exception as e:
            return {
                'batch_id': batch_id,
                'dispensary': 'trulieve',
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