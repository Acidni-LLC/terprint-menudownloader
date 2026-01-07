"""
Sunburn Dispensary Download Module
Handles data collection from Sunburn dispensary API
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
grandparent_dir = os.path.dirname(parent_dir)
sys.path.extend([current_dir, parent_dir, grandparent_dir, 
                os.path.join(grandparent_dir, "menus")])

class SunburnDownloader:
    """Sunburn dispensary data downloader"""
    
    def __init__(self, output_dir: str, azure_manager=None):
        self.output_dir = output_dir
        self.dispensary_name = 'Sunburn'
        self.azure_manager = azure_manager
        
    def download(self) -> List[Tuple[str, Dict]]:
        """Download Sunburn dispensary data"""
        print(f"Starting {self.dispensary_name} download...")
        
        try:
            # Import Sunburn module
            from menuSunburn import SunburnAPIClient
            
            results = []
            
            # Initialize client
            print(f"   Initializing {self.dispensary_name} API client...")
            client = SunburnAPIClient()
            
            # Try to get products
            print(f"   Attempting {self.dispensary_name} data collection (trying all methods)...")
            products = client.try_all_methods()
            
            if products:
                # Create filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sunburn_products_{timestamp}.json"
                
                # Add metadata
                data_with_metadata = {
                    'timestamp': timestamp,
                    'dispensary': 'sunburn',
                    'download_time': datetime.now().isoformat(),
                    'downloader_version': '1.0',
                    'product_count': len(products) if isinstance(products, list) else 0,
                    'method_used': 'try_all_methods',
                    'products': products
                }
                
                # Save to Azure Data Lake if available
                if self.azure_manager:
                    try:
                        date_folder = datetime.now().strftime("%Y/%m/%d")
                        azure_path = f"dispensaries/sunburn/{date_folder}/{filename}"
                        
                        success = self.azure_manager.save_json_to_data_lake(
                            json_data=data_with_metadata,
                            file_path=azure_path,
                            overwrite=True
                        )
                        
                        if success:
                            filepath = f"azure://{azure_path}"
                            file_size = len(json.dumps(data_with_metadata))
                            print(f"   SUCCESS: {self.dispensary_name}: {data_with_metadata['product_count']} products saved to Azure ({file_size:,} bytes)")
                            print(f"      Saved to: {azure_path}")
                            results.append((filepath, data_with_metadata))
                        else:
                            raise Exception(f"Failed to save to Azure Data Lake: {azure_path}")
                    except Exception as azure_error:
                        error_msg = f"{self.dispensary_name}: Failed to save to Azure: {azure_error}"
                        print(f"   ERROR: {error_msg}")
                        return []
                else:
                    error_msg = f"{self.dispensary_name}: Azure Data Lake Manager not available"
                    print(f"   ERROR: {error_msg}")
                    return []
                
            else:
                error_msg = f"{self.dispensary_name}: No data received (likely blocked by anti-bot protection)"
                print(f"   WARNING: {error_msg}")
                # Don't raise exception for Sunburn since it's expected to fail
                return []
            
            return results
            
        except ImportError as e:
            error_msg = f"Could not import {self.dispensary_name} module: {e}"
            print(f"ERROR: {error_msg}")
            print(f"   Check that menuSunburn.py exists in: {os.path.join(grandparent_dir, 'menus')}")
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"{self.dispensary_name} download failed: {e}"
            print(f"WARNING: {error_msg}")
            # Don't raise exception for Sunburn since it's expected to fail
            return []
    
    def get_config(self) -> Dict:
        """Get downloader configuration"""
        return {
            'name': self.dispensary_name,
            'output_dir': self.output_dir,
            'enabled': False  # Disabled by default due to anti-bot protection
        }