"""
MÜV Menu API Module
Handles API calls to the MÜV dispensary system
"""
import requests
import json
import os
from typing import Dict, List, Optional

# Load configuration
def load_config(config_path: str = None) -> Dict:
    """Load configuration from JSON file"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "menu_config.json")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
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
                "page_size": 100,
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

# MÜV SweedPOS category IDs (discovered from API filter options 2025-06-19)
# These IDs are returned by the GetProductList endpoint in the filters.category.options array
MUV_CATEGORY_IDS = {
    "Concentrates": 3483,
    "Vapes": 3484,
    "Flower": 3485,
    "Pre-Rolls": 3486,
    "Accessories": 3487,
    "Edibles": 3488,
    "Apparel": 3489,
    "Topicals": 3490,
    "Oral Products": 3491,
}

# Default categories to download - Flower, Concentrates, and Vapes only
# These are the categories with meaningful terpene/cannabinoid lab data
MUV_DEFAULT_CATEGORIES = [
    MUV_CATEGORY_IDS["Flower"],         # 3485
    MUV_CATEGORY_IDS["Concentrates"],   # 3483
    MUV_CATEGORY_IDS["Vapes"],          # 3484
]


def get_muv_products(store_id: str, config: Dict = None, category_ids: List[int] = None) -> Optional[Dict]:
    """
    Send a request to the MÜV API with specific store ID

    Args:
        store_id (str): Store ID to include in headers
        config (dict, optional): Configuration dict, uses global CONFIG if not provided
        category_ids (list[int], optional): SweedPOS category IDs to fetch.
            Defaults to MUV_DEFAULT_CATEGORIES (Flower, Concentrates, Vapes,
            Pre-Rolls, Edibles, Topicals, Oral Products).
    
    Returns:
        dict: JSON response from the API or None if failed
    """
    if config is None:
        config = CONFIG

    if category_ids is None:
        category_ids = MUV_DEFAULT_CATEGORIES
        
    url = "https://web-ui-production.sweedpos.com/_api/proxy/Products/GetProductList"

    headers = {
        "Content-Type": "application/json",
        "Storeid": str(store_id),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
    }

    api_settings = config.get("api_settings", {})
    download_settings = config.get("download_settings", {})

    payload = {
        "filters": {"category": category_ids},
        "page": 1,
        "pageSize": api_settings.get("page_size", 100),
        "sortingMethodId": api_settings.get("sorting_method_id", 7),
        "searchTerm": "",
        "platformOs": api_settings.get("platform_os", "web"),
        "sourcePage": 0
    }

    try:
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=download_settings.get("timeout", 30)
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"MÜV API request failed for store {store_id}: {e}")
        return None


def get_muv_extended_lab_data(store_id: str, variant_id: str, config: Dict = None) -> Optional[Dict]:
    """
    Get extended lab data (detailed terpene + cannabinoid percentages) for a specific variant.

    Uses the Sweed POS GetExtendedLabdata endpoint which returns individual terpene
    and cannabinoid percentages plus the COA URL with batch date.

    Args:
        store_id: MÜV store ID for the Storeid header
        variant_id: Product variant ID
        config: Optional config dict

    Returns:
        dict: Extended lab data with terpenes, thc, cbd, and fullLabDataUrl, or None
    """
    if config is None:
        config = CONFIG

    url = "https://web-ui-production.sweedpos.com/_api/proxy/Products/GetExtendedLabdata"

    headers = {
        "Content-Type": "application/json",
        "Storeid": str(store_id),
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
    }

    payload = {"variantId": str(variant_id)}

    download_settings = config.get("download_settings", {})

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=download_settings.get("timeout", 30)
        )
        response.raise_for_status()
        data = response.json()

        # Return data if it contains any lab information
        if data and isinstance(data, dict):
            return data
        return None
    except Exception:
        # Lab data is optional - don't log errors for every product
        return None
