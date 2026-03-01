import requests
import json
import os
import logging
import urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Dict, List

# Set up logger
logger = logging.getLogger(__name__)

# Load configuration
def load_config(config_path: str = None) -> Dict:
    """Load configuration from JSON file"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "menu_config.json")
    
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found at {config_path}, using defaults")
        return {
            "download_settings": {
                "max_workers": 10,
                "timeout": 30,
                "retry_attempts": 3,
                "retry_delay": 2
            },
            "api_settings": {
                "page_size": 50,
                "sorting_method_id": 7,
                "platform_os": "web"
            },
            "output_settings": {
                "output_dir": "muv_menus",
                "save_summary": True,
                "indent": 2
            }
        }

# Load config at module level
CONFIG = load_config()

def load_trulieve_store_ids(csv_path: str = None) -> List[str]:
    """Load Trulieve store location slugs from CSV file.

    Supports multiple CSV formats by attempting common column names
    such as 'location', 'storecode', 'code', 'slug', or falling back
    to the first non-numeric, non-empty column value per row.
    """
    if csv_path is None:
        # Load store_ids_csv path from config, default to storeid_location_list.csv
        csv_filename = CONFIG.get("trulieve_settings", {}).get("store_ids_csv", "storeid_location_list.csv")
        csv_path = os.path.join(os.path.dirname(__file__), csv_filename)

    stores = []
    try:
        import csv
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            # Try DictReader first to use header names when available
            reader = csv.DictReader(f)
            if reader.fieldnames:
                # iterate rows and look for a suitable slug in known columns
                for row in reader:
                    slug = None
                    # common candidate keys in order of preference
                    candidates = ['location', 'storecode', 'store_code', 'code', 'slug', 'storeid', 'store_id']
                    for cand in candidates:
                        for fk in reader.fieldnames:
                            if fk and fk.strip().lower() == cand:
                                slug = (row.get(fk) or '').strip()
                                break
                        if slug:
                            break

                    # fallback: first non-numeric, non-empty value in the row
                    if not slug:
                        for fk in reader.fieldnames:
                            val = (row.get(fk) or '').strip()
                            if val and not val.isdigit():
                                slug = val
                                break

                    if slug:
                        stores.append(slug)
            else:
                # No header found - fallback to simple reader
                f.seek(0)
                simple = csv.reader(f)
                for r in simple:
                    if not r:
                        continue
                    # pick first non-numeric, non-empty cell
                    for c in r:
                        v = c.strip()
                        if v and not v.isdigit():
                            stores.append(v)
                            break

        print(f"Loaded {len(stores)} Trulieve store locations from {csv_path}")
    except Exception as e:
        print(f"Failed to load Trulieve store IDs from {csv_path}: {e}")
        # Fallback to some default stores
        stores = ["palm_coast", "oakland_park", "port_orange"]

    return stores

def get_trulieve_store_category_configs(store_ids_or_dev_mode=None, category_ids=None) -> List[str]:
    """Generate store:category configurations from config and CSV
    
    Can be called in two ways:
    1. get_trulieve_store_category_configs(dev_mode=True/False) - uses config-based store/category lists
    2. get_trulieve_store_category_configs(store_ids, category_ids) - uses provided lists directly
    """
    trulieve_config = CONFIG.get("trulieve_settings", {})
    default_category_ids = trulieve_config.get("category_ids", ["MjA4", "MjM3", "MjA5"])  # Edibles (Ng==) excluded
    dev_stores = trulieve_config.get("dev_stores", ["palm_coast", "oakland_park", "port_orange"])
    
    # Determine if called with dev_mode (bool) or store_ids (list)
    if isinstance(store_ids_or_dev_mode, bool):
        # Called with dev_mode parameter
        dev_mode = store_ids_or_dev_mode
        if dev_mode:
            store_ids = dev_stores
        else:
            store_ids = load_trulieve_store_ids()
        category_ids = default_category_ids
    elif isinstance(store_ids_or_dev_mode, list):
        # Called with store_ids list directly
        store_ids = store_ids_or_dev_mode
        if category_ids is None:
            category_ids = default_category_ids
    elif store_ids_or_dev_mode is None:
        # Default behavior - use all stores
        store_ids = load_trulieve_store_ids()
        category_ids = default_category_ids
    else:
        # Fallback
        store_ids = load_trulieve_store_ids()
        category_ids = default_category_ids
    
    configs = []
    for store_id in store_ids:
        for category_id in category_ids:
            configs.append(f"{store_id}:{category_id}")
    
    return configs

class TrulieveAPIClient:
    """Automated Trulieve API client using working browser request format"""
    
    def __init__(self, default_store_id="palm_coast", config: Dict = None):
        if config is None:
            config = CONFIG
        self.config = config
        self.download_settings = config.get("download_settings", {})
        self.api_settings = config.get("api_settings", {})
        self.timeout = self.download_settings.get("timeout", 30)
        self.default_page_size = self.api_settings.get("page_size", 50)  # Use 50 as default to avoid server errors
        self.debug = self.api_settings.get("debug", False)
        self.base_url = "https://www.trulieve.com/api/graphql"
        self.default_store_id = default_store_id
        self.session = requests.Session()
        
        # Use the exact headers from the working browser request
        self.session.headers.update({
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "checkouttype": "pickup",
            "priority": "u=1, i",
            "referer": "https://www.trulieve.com/category/flower",
            "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
            "x-pylot-backend": "trulieve_prod",
            "x-pylot-query": "products"
        })
        
        # Base cookies - we'll update store-specific ones as needed
        self.base_cookies = {
            "trulieve_fe_url": "true",
            "trulieve_fe_cluster": "live",
            "state_name": "FL",
            "checkouttype": "pickup"
        }
    
    def set_store(self, store_id):
        """Set the store ID for requests"""
        self.session.headers["store"] = store_id
        
        # Update cookies with store ID
        cookies = self.base_cookies.copy()
        cookies["store_id"] = store_id
        
        # Convert cookies to cookie string
        cookie_string = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        self.session.headers["cookie"] = cookie_string
    
    def get_products_url_encoded(self, store_id=None, category_uid=None, page_size=None, current_page=1):
        """Get products using URL-encoded GET request like the browser"""
        
        if page_size is None:
            page_size = self.default_page_size
        
        if store_id:
            self.set_store(store_id)
        elif self.default_store_id:
            self.set_store(self.default_store_id)
        
        # Build search criteria
        search_criteria = []
        if category_uid and category_uid.strip():
            search_criteria.append({
                "attribute_code": "category_uid",
                "filter_action": "EQ",
                "filter_value": category_uid
            })
        
        # GraphQL query (matching the working browser request)
        query = """
        query products($searchCriteria:[SearchCriteriaInput!]!,$pageSize:Int=50,$currentPage:Int=1,$sort:ProductAttributeSortInput={}){
            products(searchCriteria:$searchCriteria pageSize:$pageSize currentPage:$currentPage sort:$sort){
                aggregations{
                    __typename 
                    attribute_code 
                    count 
                    label 
                    options{
                        __typename 
                        count 
                        label 
                        value
                    }
                }
                __typename 
                sort_fields{
                    __typename 
                    default 
                    options{
                        __typename 
                        label 
                        value
                    }
                }
                items{
                    __typename 
                    id 
                    name 
                    available_quantity
                    stock_status 
                    custom_attributes_product{
                        label 
                        code 
                        value
                    }
                    last_chance 
                    opps_promo{
                        promo_id 
                        promo_name
                    }
                    price_range{
                        __typename 
                        minimum_price{
                            __typename 
                            regular_price{
                                __typename 
                                value
                            }
                            final_price{
                                __typename 
                                value
                            }
                            discount{
                                __typename 
                                amount_off
                            }
                        }
                    }
                    sku 
                    small_image{
                        __typename 
                        url
                    }
                    url_key 
                    categories{
                        name 
                        url_path
                    }
                    ... on ConfigurableProduct{
                        configurable_options{
                            __typename 
                            attribute_code 
                            label 
                            values{
                                __typename 
                                value_index 
                                label 
                                uid 
                                swatch_data{
                                    __typename 
                                    value
                                    ... on ImageSwatchData{
                                        thumbnail 
                                        __typename
                                    }
                                }
                            }
                        }
                        variants{
                            __typename 
                            attributes{
                                __typename 
                                code 
                                value_index 
                                label 
                                uid
                            }
                            product{
                                __typename 
                                id 
                                small_image{
                                    __typename 
                                    url
                                }
                                price_range{
                                    __typename 
                                    minimum_price{
                                        __typename 
                                        regular_price{
                                            __typename 
                                            value
                                        }
                                        final_price{
                                            __typename 
                                            value
                                        }
                                        discount{
                                            __typename 
                                            amount_off
                                        }
                                    }
                                }
                                sku 
                                stock_status 
                                thc_percentage 
                                dominant_terpene 
                                dominant_terpene_percentage 
                                secondary_terpene 
                                secondary_terpene_percentage 
                                terciary_terpene 
                                terciary_terpene_percentage 
                                total_terpene_percentage
                            }
                        }
                        __typename
                    }
                }
                page_info{
                    __typename 
                    total_pages 
                    current_page
                }
                total_count
            }
        }
        """
        
        # Variables (matching the working browser request)
        variables = {
            "currentPage": current_page,
            "pageSize": page_size,
            "searchCriteria": search_criteria,
            "sort": {}
        }
        
        # URL encode the parameters like the browser does
        params = {
            "query": query,
            "operationName": "products",
            "variables": json.dumps(variables)
        }
        
        try:
            # Log to both console and Application Insights
            log_msg = f"Trulieve API: store={store_id}, category={category_uid}, page={current_page}, page_size={page_size}"
            print(f"   [SIGNAL] {log_msg}")
            logger.info(log_msg)
            
            # Use GET request like the browser
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if 'data' in result and result['data'] and 'products' in result['data']:
                    products = result['data']['products']
                    item_count = len(products.get('items', [])) if products else 0
                    total_count = products.get('total_count', 0) if products else 0
                    log_msg = f"Trulieve SUCCESS: store={store_id}, category={category_uid}, items={item_count}, total={total_count}"
                    print(f"   [OK] {log_msg}")
                    logger.info(log_msg)
                    return products
                elif 'errors' in result:
                    log_msg = f"Trulieve GraphQL ERROR: store={store_id}, category={category_uid}, errors={result['errors']}"
                    print(f"   [FAIL] {log_msg}")
                    logger.error(log_msg)
                    return None
                else:
                    log_msg = f"Trulieve unexpected response: store={store_id}, category={category_uid}"
                    print(f"   [WARN] {log_msg}")
                    logger.warning(log_msg)
                    return None
            else:
                log_msg = f"Trulieve HTTP {response.status_code}: store={store_id}, category={category_uid}"
                print(f"   [FAIL] {log_msg}")
                logger.error(f"{log_msg}, response={response.text[:200]}")
                return None
                
        except Exception as e:
            log_msg = f"Trulieve EXCEPTION: store={store_id}, category={category_uid}, error={e}"
            print(f"   [FAIL] {log_msg}")
            logger.exception(log_msg)
            return None
    
    def get_all_products_for_store(self, store_id, category_uid=None, max_pages=20, page_size=None):
        """Get all products for a store across all pages"""
        
        if page_size is None:
            page_size = self.default_page_size
        
        all_products = []
        current_page = 1
        total_pages = 1
        
        while current_page <= total_pages and current_page <= max_pages:
            logger.debug(f"Trulieve fetching page {current_page} for store={store_id}, category={category_uid}")
            
            products_data = self.get_products_url_encoded(
                store_id=store_id,
                category_uid=category_uid,
                current_page=current_page,
                page_size=page_size
            )
            
            if products_data and isinstance(products_data, dict):
                # Update total pages
                page_info = products_data.get('page_info', {})
                if page_info:
                    total_pages = page_info.get('total_pages', 1)
                
                # Add items
                items = products_data.get('items', [])
                if items:
                    all_products.extend(items)
                
                current_page += 1
            else:
                logger.warning(f"Trulieve failed to get page {current_page} for store={store_id}, category={category_uid}")
                break
        
        logger.info(f"Trulieve collection complete: store={store_id}, category={category_uid}, products={len(all_products)}")
        return all_products

# Store configurations from your config file
# Set DEV_MODE = True to use only test stores, False for all stores
DEV_MODE = os.getenv('TRULIEVE_DEV_MODE', 'false').lower() == 'true'

# Development test stores (for faster testing) - now loaded from config
DEV_STORE_CATEGORY_CONFIG = get_trulieve_store_category_configs(True)

# Production - all store configurations - now loaded from CSV and config
PROD_STORE_CATEGORY_CONFIG = get_trulieve_store_category_configs(False)

# Select configuration based on mode
STORE_CATEGORY_CONFIG = DEV_STORE_CATEGORY_CONFIG if DEV_MODE else PROD_STORE_CATEGORY_CONFIG

def test_browser_format():
    """Test using the exact browser request format"""
    
    print("[TEST] TESTING BROWSER FORMAT")
    print("="*40)
    
    client = TrulieveAPIClient()
    
    # Test the specific working example from your browser
    print("\n[TARGET] Testing palm_coast:MjA3 (from browser example)")
    print("-" * 40)
    
    # Use the exact parameters from the working browser request
    products = client.get_products_url_encoded(
        store_id="palm_coast",
        category_uid="MjA3",  # This was in your working browser request
        page_size=None,  # Use config default
        current_page=1
    )
    
    if products:
        total_count = products.get('total_count', 0)
        items = products.get('items', [])
        
        print(f"[OK] SUCCESS! Found {total_count} total products")
        print(f"[BOX] Retrieved {len(items)} products in this page")
        
        if items:
            sample = items[0]
            print(f"[LIST] Sample product: {sample.get('name', 'No name')}")
            print(f"[TAG]  SKU: {sample.get('sku', 'No SKU')}")
            print(f"[PRICE] Price: {sample.get('price_range', {}).get('minimum_price', {}).get('final_price', {}).get('value', 'No price')}")
            
            # Check for terpene data
            if 'variants' in sample and sample['variants']:
                variant = sample['variants'][0]
                thc = variant.get('product', {}).get('thc_percentage', 'N/A')
                terpenes = variant.get('product', {}).get('total_terpene_percentage', 'N/A')
                print(f"[LEAF] THC: {thc}%, Terpenes: {terpenes}%")
        
        return True
    else:
        print("[FAIL] Failed to get products with browser format")
        return False

def collect_all_trulieve_data_browser_format(dev_mode=None, store_ids=None, category_ids=None):
    """Collect data using the browser request format
    
    Args:
        dev_mode: Override DEV_MODE setting. True for dev stores only, False for all stores, None to use env setting
    """
    
    print("[ROCKET] COLLECTING TRULIEVE DATA (BROWSER FORMAT)")
    print("="*60)
    
    # Determine which config to use
    if store_ids is not None and category_ids is not None:
        # Use provided store_ids and category_ids
        config_list = get_trulieve_store_category_configs(store_ids, category_ids)
        use_dev = False  # Not relevant when custom lists provided
        mode_name = f"CUSTOM ({len(store_ids)} stores × {len(category_ids)} categories = {len(config_list)} combinations)"
    elif dev_mode is not None:
        use_dev = dev_mode
        config_list = DEV_STORE_CATEGORY_CONFIG if dev_mode else PROD_STORE_CATEGORY_CONFIG
        mode_name = "DEVELOPMENT" if dev_mode else "PRODUCTION"
    else:
        use_dev = DEV_MODE
        config_list = STORE_CATEGORY_CONFIG
        mode_name = "CONFIG-BASED"
    
    print(f"[LIST] MODE: {mode_name} ({len(config_list)} store/category combinations)")
    
    client = TrulieveAPIClient()
    
    # Skip browser format test - we know it works, saves ~1-2 seconds
    # if not test_browser_format():
    #     print("[FAIL] Browser format test failed, stopping")
    #     return None
    
    all_store_data = {
        "collection_timestamp": datetime.now().isoformat(),
        "stores": {},
        "combined_products": [],
        "summary": {
            "total_products": 0,
            "successful_stores": 0,
            "failed_stores": 0,
            "working_configurations": [],
            "failed_configurations": []
        }
    }
    
    print(f"\n[STORE] Processing {len(config_list)} store configurations in parallel...")
    logger.info(f"Trulieve starting parallel processing of {len(config_list)} store/category combinations")
    
    # Thread-safe lock for updating shared data
    data_lock = Lock()
    
    def process_store_category(config, index):
        """Process a single store/category combination"""
        store_id, category_id = config.split(":")
        
        # Create a separate client for this thread
        thread_client = TrulieveAPIClient()
        
        print(f"\n[{index}/{len(config_list)}] {store_id}:{category_id}")
        print("-" * 50)
        logger.info(f"Trulieve processing [{index}/{len(config_list)}] store={store_id}, category={category_id}")
        
        result = {
            'config': config,
            'store_id': store_id,
            'category_id': category_id,
            'success': False
        }
        
        try:
            # Get all products for this store/category directly (no test request)
            all_products = thread_client.get_all_products_for_store(store_id, category_id)
            
            if all_products:
                # Add store info to each product
                for product in all_products:
                    product['_store_info'] = {
                        "store_id": store_id,
                        "category_id": category_id,
                        "config": config
                    }
                
                result.update({
                    'success': True,
                    'products_count': len(all_products),
                    'total_available': len(all_products),
                    'products': all_products
                })
                
                print(f"   [OK] Collected {len(all_products)} products for {store_id}:{category_id}")
                logger.info(f"Trulieve collected [{index}/{len(config_list)}] store={store_id}, category={category_id}, products={len(all_products)}")
            else:
                logger.warning(f"Trulieve no products [{index}/{len(config_list)}] store={store_id}, category={category_id}")
                result['error'] = 'No products found'
                
        except Exception as e:
            logger.exception(f"Trulieve error [{index}/{len(config_list)}] store={store_id}, category={category_id}, error={e}")
            result['error'] = str(e)
        
        return result
    
    # Process all store/category combinations in parallel
    max_workers = CONFIG.get("download_settings", {}).get("max_workers", 10)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_config = {
            executor.submit(process_store_category, config, i): config 
            for i, config in enumerate(config_list, 1)
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_config):
            config = future_to_config[future]
            try:
                result = future.result()
                
                # Thread-safe update of shared data structure
                with data_lock:
                    all_store_data['stores'][config] = {
                        "store_id": result['store_id'],
                        "category_id": result['category_id'],
                        "success": result['success']
                    }
                    
                    if result['success']:
                        all_store_data['stores'][config].update({
                            "products_count": result['products_count'],
                            "total_available": result['total_available'],
                            "products": result['products']
                        })
                        all_store_data['combined_products'].extend(result['products'])
                        all_store_data['summary']['total_products'] += result['products_count']
                        all_store_data['summary']['successful_stores'] += 1
                        all_store_data['summary']['working_configurations'].append(config)
                    else:
                        all_store_data['stores'][config]['error'] = result.get('error', 'Unknown error')
                        all_store_data['summary']['failed_stores'] += 1
                        all_store_data['summary']['failed_configurations'].append(config)
                        
            except Exception as e:
                print(f"  [FAIL] Exception processing {config}: {e}")
                with data_lock:
                    all_store_data['stores'][config] = {
                        "store_id": config.split(':')[0],
                        "category_id": config.split(':')[1],
                        "success": False,
                        "error": str(e)
                    }
                    all_store_data['summary']['failed_stores'] += 1
                    all_store_data['summary']['failed_configurations'].append(config)
    
    return all_store_data

def save_trulieve_data(data):
    """Save the collected data to files"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save complete data
    filename = f"trulieve_complete_data_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"[SAVED] Complete data saved to: {filename}")
    
    # Save products-only file
    products_filename = f"trulieve_products_{timestamp}.json"
    products_data = {
        "timestamp": data["collection_timestamp"],
        "total_products": len(data["combined_products"]),
        "successful_stores": data["summary"]["successful_stores"],
        "products": data["combined_products"]
    }
    
    with open(products_filename, 'w', encoding='utf-8') as f:
        json.dump(products_data, f, indent=2, ensure_ascii=False)
    
    print(f"[SAVED] Products-only saved to: {products_filename}")
    
    return filename, products_filename

if __name__ == "__main__":
    print("[TEST] Testing Trulieve API with exact browser format...")
    
    # Collect data using browser format
    all_data = collect_all_trulieve_data_browser_format()
    
    if all_data:
        # Print summary
        print(f"\n[SUMMARY] COLLECTION SUMMARY")
        print("="*40)
        print(f"[OK] Successful stores: {all_data['summary']['successful_stores']}")
        print(f"[FAIL] Failed stores: {all_data['summary']['failed_stores']}")
        print(f"[BOX] Total products: {all_data['summary']['total_products']}")
        
        if all_data['summary']['working_configurations']:
            print(f"\n[SUCCESS] Working configurations:")
            for config in all_data['summary']['working_configurations']:
                store_data = all_data['stores'][config]
                print(f"   {config}: {store_data['products_count']} products")
        
        # Save data
        if all_data['summary']['total_products'] > 0:
            complete_file, products_file = save_trulieve_data(all_data)
            print(f"\n[ROCKET] SUCCESS! Data collection complete.")
            print(f"Ready for Azure Data Lake upload!")
        else:
            print(f"\n[WARN] No products collected")
    else:
        print(f"\n[FAIL] Collection failed")
