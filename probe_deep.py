"""
Phase 0b: Deep investigation of failed states
- Check 550 response bodies
- Try alternate slug formats (dash vs underscore)
- Try without store_id cookie (state-level only)
- Check GA with different category IDs
- Inspect WV product structure for terpene fields
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

QUERY = """
query products($searchCriteria:[SearchCriteriaInput!]!,$pageSize:Int=50,$currentPage:Int=1,$sort:ProductAttributeSortInput={}){
    products(searchCriteria:$searchCriteria pageSize:$pageSize currentPage:$currentPage sort:$sort){
        items{
            id name sku stock_status available_quantity
            categories{ name url_path }
            price_range{ minimum_price{ final_price{ value } } }
            ... on ConfigurableProduct{
                configurable_options{ attribute_code label values{ label uid } }
                variants{
                    product{
                        sku stock_status
                        thc_percentage
                        dominant_terpene dominant_terpene_percentage
                        secondary_terpene secondary_terpene_percentage
                        terciary_terpene terciary_terpene_percentage
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


def make_request(state, store, cat_uid="MjA4", page_size=3):
    cookie_str = f"trulieve_fe_url=true; trulieve_fe_cluster=live; state_name={state}; checkouttype=pickup; store_id={store}"
    headers = HEADERS.copy()
    headers["cookie"] = cookie_str
    headers["store"] = store
    
    variables = {
        "currentPage": 1,
        "pageSize": page_size,
        "searchCriteria": [{"attribute_code": "category_uid", "filter_action": "EQ", "filter_value": cat_uid}],
        "sort": {},
    }
    params = {"query": QUERY, "operationName": "products", "variables": json.dumps(variables)}
    
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
    return resp


def test_550_bodies():
    """Check what the 550 error responses actually contain."""
    print("=" * 80)
    print("TEST 1: What do HTTP 550 responses say?")
    print("=" * 80)
    
    failed_states = [
        ("AZ", "apache_junction"),
        ("PA", "camp_hill"),
        ("MD", "rockville"),
        ("CT", "bristol"),
        ("CA", "paso_robles"),
    ]
    
    for state, store in failed_states:
        resp = make_request(state, store)
        print(f"\n  {state} ({store}): HTTP {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('content-type', 'unknown')}")
        body = resp.text[:500]
        print(f"  Body: {body}")
        time.sleep(0.3)


def test_alternate_slugs():
    """Try different slug formats - maybe AZ uses dashes not underscores."""
    print("\n" + "=" * 80)
    print("TEST 2: Alternate store slug formats for AZ")
    print("=" * 80)
    
    az_slugs = [
        "apache_junction",      # underscore (FL pattern)
        "apache-junction",      # dash
        "apachejunction",       # no separator
        "Apache Junction",      # title case
        "apache_junction_az",   # with state suffix
        "avondale",             # single word (no separator needed)
        "bisbee",               # single word
        "casa_grande",          # underscore
        "casa-grande",          # dash
    ]
    
    for slug in az_slugs:
        resp = make_request("AZ", slug)
        status = resp.status_code
        total = 0
        if status == 200:
            try:
                data = resp.json()
                total = data.get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if status == 200 and total > 0 else "⚠️" if status == 200 else "❌"
        print(f"  {symbol} AZ + '{slug}' → HTTP {status}, {total} products")
        time.sleep(0.3)
    
    # Also try PA with dashes
    print(f"\n  PA variants:")
    pa_slugs = ["camp_hill", "camp-hill", "camphill", "coatesville", "harrisburg", "lancaster"]
    for slug in pa_slugs:
        resp = make_request("PA", slug)
        status = resp.status_code
        total = 0
        if status == 200:
            try:
                data = resp.json()
                total = data.get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if status == 200 and total > 0 else "⚠️" if status == 200 else "❌"
        print(f"  {symbol} PA + '{slug}' → HTTP {status}, {total} products")
        time.sleep(0.3)


def test_no_store_cookie():
    """Try requesting with just state cookie, no store_id."""
    print("\n" + "=" * 80)
    print("TEST 3: State-only cookie (no store_id)")
    print("=" * 80)
    
    for state in ["AZ", "PA", "GA", "MD", "CT", "CA"]:
        cookie_str = f"trulieve_fe_url=true; trulieve_fe_cluster=live; state_name={state}; checkouttype=pickup"
        headers = HEADERS.copy()
        headers["cookie"] = cookie_str
        # Don't set 'store' header either
        
        variables = {
            "currentPage": 1,
            "pageSize": 3,
            "searchCriteria": [{"attribute_code": "category_uid", "filter_action": "EQ", "filter_value": "MjA4"}],
            "sort": {},
        }
        params = {"query": QUERY, "operationName": "products", "variables": json.dumps(variables)}
        
        resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
        status = resp.status_code
        total = 0
        if status == 200:
            try:
                data = resp.json()
                total = data.get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if status == 200 and total > 0 else "⚠️" if status == 200 else "❌"
        print(f"  {symbol} {state} (no store) → HTTP {status}, {total} products")
        time.sleep(0.3)


def test_wv_terpenes():
    """Deep inspect WV product data structure."""
    print("\n" + "=" * 80)
    print("TEST 4: WV Flower product deep inspection (terpene fields)")
    print("=" * 80)
    
    resp = make_request("WV", "morgantown", "MjA4", page_size=2)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("data", {}).get("products", {}).get("items", [])
        for item in items[:2]:
            print(f"\n  Product: {item.get('name')}")
            print(f"  SKU: {item.get('sku')}")
            print(f"  Categories: {[c.get('name') for c in item.get('categories', [])]}")
            
            variants = item.get("variants", [])
            print(f"  Variants: {len(variants)}")
            for v in variants[:2]:
                prod = v.get("product", {})
                print(f"    Variant SKU: {prod.get('sku')}")
                print(f"    THC %: {prod.get('thc_percentage')}")
                print(f"    Dominant Terpene: {prod.get('dominant_terpene')} ({prod.get('dominant_terpene_percentage')})")
                print(f"    Secondary Terpene: {prod.get('secondary_terpene')} ({prod.get('secondary_terpene_percentage')})")
                print(f"    Terciary Terpene: {prod.get('terciary_terpene')} ({prod.get('terciary_terpene_percentage')})")
                print(f"    Total Terpene %: {prod.get('total_terpene_percentage')}")
            
            config_opts = item.get("configurable_options", [])
            print(f"  Config Options: {len(config_opts)}")
            for opt in config_opts:
                print(f"    {opt.get('attribute_code')}: {opt.get('label')}")
                vals = opt.get("values", [])[:3]
                for val in vals:
                    print(f"      - {val.get('label')}")


def test_ga_categories():
    """GA returns 0 products - maybe different category IDs?"""
    print("\n" + "=" * 80)
    print("TEST 5: GA - try without category filter (all products)")
    print("=" * 80)
    
    # Try with no category filter
    cookie_str = "trulieve_fe_url=true; trulieve_fe_cluster=live; state_name=GA; checkouttype=pickup; store_id=columbus"
    headers = HEADERS.copy()
    headers["cookie"] = cookie_str
    headers["store"] = "columbus"
    
    variables = {
        "currentPage": 1,
        "pageSize": 10,
        "searchCriteria": [],  # No category filter
        "sort": {},
    }
    params = {"query": QUERY, "operationName": "products", "variables": json.dumps(variables)}
    
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        products = data.get("data", {}).get("products", {})
        total = products.get("total_count", 0)
        items = products.get("items", [])
        print(f"  GA (columbus) no filter: {total} total products, {len(items)} returned")
        for item in items[:5]:
            cats = [c.get("name") for c in item.get("categories", [])]
            print(f"    - {item.get('name')} | SKU: {item.get('sku')} | Cats: {cats}")
    else:
        print(f"  GA (columbus) no filter: HTTP {resp.status_code}")
    
    # Also try other GA stores
    print(f"\n  Other GA stores:")
    for slug in ["evans", "macon", "marietta", "newnan", "pooler"]:
        resp2 = make_request("GA", slug)
        total2 = 0
        if resp2.status_code == 200:
            try:
                total2 = resp2.json().get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if total2 > 0 else "⚠️" if resp2.status_code == 200 else "❌"
        print(f"    {symbol} GA + '{slug}' → HTTP {resp2.status_code}, {total2} products")
        time.sleep(0.3)


if __name__ == "__main__":
    test_550_bodies()
    test_alternate_slugs()
    test_no_store_cookie()
    test_wv_terpenes()
    test_ga_categories()
    
    print("\n\n✅ All deep-dive tests complete!")
