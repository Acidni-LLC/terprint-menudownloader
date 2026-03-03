"""
Phase 0: Trulieve Multi-State API Probe
Tests whether the same GraphQL endpoint + category IDs work across all states.
Just changes the state_name cookie and store_id.
"""
import requests
import json
import time

BASE_URL = "https://www.trulieve.com/api/graphql"

HEADERS = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9",
    "checkouttype": "pickup",
    "referer": "https://www.trulieve.com/category/flower",
    "sec-ch-ua": '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "x-pylot-backend": "trulieve_prod",
    "x-pylot-query": "products",
}

# Representative store slug per state (from trulieve.com/dispensaries)
STATE_STORES = {
    "FL": "palm_coast",
    "AZ": "apache_junction",
    "PA": "camp_hill",
    "WV": "morgantown",
    "GA": "columbus",
    "MD": "rockville",
    "CT": "bristol",
    "CA": "paso_robles",  # Note: already in FL CSV as anomaly
}

CATEGORY_IDS = {
    "Flower": "MjA4",
    "Pre-Rolls": "MjM3",
    "Vaporizers": "MjA5",
    "Edibles": "Ng==",
}

QUERY = """
query products($searchCriteria:[SearchCriteriaInput!]!,$pageSize:Int=50,$currentPage:Int=1,$sort:ProductAttributeSortInput={}){
    products(searchCriteria:$searchCriteria pageSize:$pageSize currentPage:$currentPage sort:$sort){
        items{
            id
            name
            sku
            stock_status
            available_quantity
            categories{ name }
            price_range{
                minimum_price{
                    final_price{ value }
                }
            }
            ... on ConfigurableProduct{
                configurable_options{
                    attribute_code
                    label
                    values{ label uid }
                }
                variants{
                    product{
                        sku
                        stock_status
                        thc_percentage
                        dominant_terpene
                        dominant_terpene_percentage
                        total_terpene_percentage
                    }
                }
            }
        }
        page_info{ total_pages current_page }
        total_count
    }
}
"""


def probe_state_category(state: str, store: str, cat_name: str, cat_uid: str) -> dict:
    """Probe one state+category combo and return results summary."""
    cookie_str = f"trulieve_fe_url=true; trulieve_fe_cluster=live; state_name={state}; checkouttype=pickup; store_id={store}"
    
    headers = HEADERS.copy()
    headers["cookie"] = cookie_str
    headers["store"] = store
    
    variables = {
        "currentPage": 1,
        "pageSize": 5,  # Just 5 products to test
        "searchCriteria": [
            {"attribute_code": "category_uid", "filter_action": "EQ", "filter_value": cat_uid}
        ],
        "sort": {},
    }
    
    params = {
        "query": QUERY,
        "operationName": "products",
        "variables": json.dumps(variables),
    }
    
    try:
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        status = resp.status_code
        
        if status != 200:
            return {"state": state, "store": store, "category": cat_name, "status": status, "error": f"HTTP {status}", "products": 0, "total": 0}
        
        data = resp.json()
        
        if "errors" in data:
            return {"state": state, "store": store, "category": cat_name, "status": status, "error": str(data["errors"][:1]), "products": 0, "total": 0}
        
        products_data = data.get("data", {}).get("products", {})
        items = products_data.get("items", [])
        total = products_data.get("total_count", 0)
        
        # Check for terpene data
        has_terpenes = False
        has_batch_codes = False
        sample_product = None
        sample_sku = None
        
        for item in items:
            if sample_product is None:
                sample_product = item.get("name", "")
                sample_sku = item.get("sku", "")
            
            # Check configurable_options for batch codes
            config_opts = item.get("configurable_options", [])
            for opt in config_opts:
                if opt.get("attribute_code") == "batch_code" or "batch" in opt.get("label", "").lower():
                    has_batch_codes = True
                    
            # Check variants for terpene data
            variants = item.get("variants", [])
            for v in variants:
                prod = v.get("product", {})
                if prod.get("dominant_terpene") or prod.get("total_terpene_percentage"):
                    has_terpenes = True
        
        return {
            "state": state,
            "store": store,
            "category": cat_name,
            "status": status,
            "products_returned": len(items),
            "total_count": total,
            "has_terpenes": has_terpenes,
            "has_batch_codes": has_batch_codes,
            "sample_product": sample_product,
            "sample_sku": sample_sku,
            "error": None,
        }
        
    except Exception as e:
        return {"state": state, "store": store, "category": cat_name, "status": 0, "error": str(e), "products": 0, "total": 0}


def main():
    print("=" * 100)
    print("TRULIEVE MULTI-STATE API PROBE")
    print("=" * 100)
    
    all_results = []
    
    for state, store in STATE_STORES.items():
        print(f"\n{'─' * 80}")
        print(f"  STATE: {state} | STORE: {store}")
        print(f"{'─' * 80}")
        
        for cat_name, cat_uid in CATEGORY_IDS.items():
            result = probe_state_category(state, store, cat_name, cat_uid)
            all_results.append(result)
            
            if result.get("error"):
                print(f"  ❌ {cat_name:15s} | ERROR: {result['error']}")
            else:
                terp = "🧬" if result.get("has_terpenes") else "  "
                batch = "📦" if result.get("has_batch_codes") else "  "
                sample = result.get('sample_product') or ''
                print(f"  ✅ {cat_name:15s} | {result['total_count']:4d} products | {terp} terpenes | {batch} batches | Sample: {sample[:50]}")
            
            time.sleep(0.3)  # Be polite to the API
    
    # Summary table
    print(f"\n\n{'=' * 100}")
    print("SUMMARY BY STATE")
    print(f"{'=' * 100}")
    print(f"{'State':<6} {'Store':<20} {'Flower':>8} {'Pre-Roll':>8} {'Vapes':>8} {'Edibles':>8} {'Total':>8} {'Terpenes':>10}")
    print(f"{'─' * 6} {'─' * 20} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 10}")
    
    for state, store in STATE_STORES.items():
        state_results = [r for r in all_results if r["state"] == state]
        counts = {}
        any_terpenes = False
        for r in state_results:
            counts[r["category"]] = r.get("total_count", 0)
            if r.get("has_terpenes"):
                any_terpenes = True
        
        total = sum(counts.values())
        terp_str = "✅ Yes" if any_terpenes else "❌ No"
        
        print(f"{state:<6} {store:<20} {counts.get('Flower', 0):>8} {counts.get('Pre-Rolls', 0):>8} {counts.get('Vaporizers', 0):>8} {counts.get('Edibles', 0):>8} {total:>8} {terp_str:>10}")
    
    # Save raw results
    with open("probe_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n📄 Raw results saved to probe_results.json")


if __name__ == "__main__":
    main()
