"""
Phase 0c: Follow-up investigation based on key findings:
1. No store_id → ALL states return 200 with 411 products (is this FL data leaking?)
2. WV works with store_id but has no terpene data
3. GA with store_id returns 0 products (low-THC state?)
4. AZ/PA/MD/CT/CA 550 ONLY when store_id is set

Key question: Does removing store_id return state-specific data or always FL?
"""
import requests
import json
import time

BASE_URL = "https://www.trulieve.com/api/graphql"

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
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


def make_request_custom(state, store=None, cat_uid="MjA4", page_size=5):
    cookies = {
        "trulieve_fe_url": "true",
        "trulieve_fe_cluster": "live",
        "state_name": state,
        "checkouttype": "pickup",
    }
    if store:
        cookies["store_id"] = store
    
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = HEADERS.copy()
    headers["cookie"] = cookie_str
    if store:
        headers["store"] = store
    
    search_criteria = []
    if cat_uid:
        search_criteria.append({"attribute_code": "category_uid", "filter_action": "EQ", "filter_value": cat_uid})
    
    variables = {
        "currentPage": 1,
        "pageSize": page_size,
        "searchCriteria": search_criteria,
        "sort": {},
    }
    params = {"query": QUERY, "operationName": "products", "variables": json.dumps(variables)}
    
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=15)
    return resp


def test_1_no_store_state_fingerprint():
    """Do state-only queries return DIFFERENT products or the same FL catalog?"""
    print("=" * 90)
    print("TEST 1: Are state-only (no store_id) results actually different per state?")
    print("=" * 90)
    
    state_products = {}
    for state in ["FL", "AZ", "PA", "WV", "GA", "MD"]:
        resp = make_request_custom(state, store=None, cat_uid="MjA4", page_size=10)
        if resp.status_code == 200:
            data = resp.json()
            products = data.get("data", {}).get("products", {})
            if products:
                total = products.get("total_count", 0)
                items = products.get("items", [])
                # Fingerprint: collect first 5 product names and SKUs
                names = [(i.get("name", ""), i.get("sku", "")) for i in items[:5]]
                state_products[state] = {"total": total, "names": names}
                print(f"\n  {state} (no store): {total} total products")
                for n, s in names:
                    print(f"    - {n} (SKU: {s})")
            else:
                print(f"\n  {state} (no store): products is None")
        else:
            print(f"\n  {state} (no store): HTTP {resp.status_code}")
        time.sleep(0.3)
    
    # Compare: are they all the same?
    print(f"\n  --- Comparison ---")
    fl_names = state_products.get("FL", {}).get("names", [])
    for state, info in state_products.items():
        if state == "FL":
            continue
        same = info["names"] == fl_names
        print(f"  {state} vs FL: {'SAME products ⚠️' if same else 'DIFFERENT products ✅'} (totals: {info['total']} vs {state_products['FL']['total']})")


def test_2_wv_batch_codes_coa():
    """Get WV batch codes and test COA PDF downloads."""
    print("\n" + "=" * 90)
    print("TEST 2: WV batch codes → COA URL test")
    print("=" * 90)
    
    resp = make_request_custom("WV", "morgantown", "MjA4", page_size=5)
    if resp.status_code != 200:
        print(f"  WV request failed: HTTP {resp.status_code}")
        return
    
    data = resp.json()
    items = data.get("data", {}).get("products", {}).get("items", [])
    
    batch_codes = []
    for item in items:
        for opt in item.get("configurable_options", []):
            if opt.get("attribute_code") == "batch_codes":
                for val in opt.get("values", [])[:2]:
                    batch_codes.append((item.get("name"), val.get("label")))
    
    print(f"  Found {len(batch_codes)} batch codes")
    for product_name, code in batch_codes[:6]:
        url = f"https://www.trulieve.com/content/dam/trulieve/en/lab-reports/{code}.pdf"
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            status = r.status_code
            content_type = r.headers.get("content-type", "")
            symbol = "✅" if status == 200 and "pdf" in content_type else "❌"
            print(f"  {symbol} {product_name} | Batch: {code} → HTTP {status} ({content_type[:30]})")
        except Exception as e:
            print(f"  ❌ {product_name} | Batch: {code} → Error: {e}")
        time.sleep(0.3)


def test_3_fl_store_on_az_state():
    """What happens if we use a FL store slug with AZ state? Or vice versa?"""
    print("\n" + "=" * 90)
    print("TEST 3: Cross-state store mixing")
    print("=" * 90)
    
    combos = [
        ("AZ", "palm_coast", "FL store on AZ state"),
        ("FL", "morgantown", "WV store on FL state"),
        ("WV", "palm_coast", "FL store on WV state"),
    ]
    for state, store, desc in combos:
        resp = make_request_custom(state, store, "MjA4", page_size=3)
        status = resp.status_code
        total = 0
        if status == 200:
            try:
                total = resp.json().get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if status == 200 and total > 0 else "⚠️" if status == 200 else "❌"
        print(f"  {symbol} {desc}: state={state} store={store} → HTTP {status}, {total} products")
        time.sleep(0.3)


def test_4_ga_all_products():
    """GA with store returns 0 products - try no category filter and different stores."""
    print("\n" + "=" * 90)
    print("TEST 4: GA investigation (0 products with category filter)")
    print("=" * 90)
    
    # No category filter
    resp = make_request_custom("GA", "columbus", cat_uid=None, page_size=10)
    if resp.status_code == 200:
        data = resp.json()
        products = data.get("data", {}).get("products")
        if products:
            total = products.get("total_count", 0)
            items = products.get("items", [])
            print(f"  GA (columbus) NO category filter: {total} total, {len(items)} returned")
            for i in items[:5]:
                cats = [c.get("name") for c in i.get("categories", [])]
                print(f"    - {i.get('name')} | SKU: {i.get('sku')} | Cats: {cats}")
        else:
            print(f"  GA (columbus) NO category filter: products is None")
    else:
        print(f"  GA (columbus) NO category filter: HTTP {resp.status_code}")
    
    # Try different GA store slugs
    print(f"\n  Other GA stores (with Flower category):")
    for slug in ["evans", "macon", "marietta", "newnan", "pooler"]:
        r = make_request_custom("GA", slug, "MjA4", page_size=3)
        total = 0
        if r.status_code == 200:
            try:
                total = r.json().get("data", {}).get("products", {}).get("total_count", 0)
            except:
                pass
        symbol = "✅" if total > 0 else "⚠️" if r.status_code == 200 else "❌"
        print(f"    {symbol} GA + '{slug}' → HTTP {r.status_code}, {total} flower products")
        time.sleep(0.3)


def test_5_fl_sanity_check():
    """Verify FL still works and get current product count for baseline."""
    print("\n" + "=" * 90)
    print("TEST 5: FL baseline (with store_id) - sanity check")
    print("=" * 90)
    
    for cat_name, cat_uid in [("Flower", "MjA4"), ("Pre-Rolls", "MjM3"), ("Vaporizers", "MjA5"), ("Edibles", "Ng==")]:
        resp = make_request_custom("FL", "palm_coast", cat_uid, page_size=3)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("data", {}).get("products", {}).get("total_count", 0)
            items = data.get("data", {}).get("products", {}).get("items", [])
            has_terp = any(
                v.get("product", {}).get("dominant_terpene") 
                for i in items for v in i.get("variants", [])
            )
            print(f"  ✅ FL {cat_name}: {total} products, terpenes: {'Yes' if has_terp else 'No'}")
        else:
            print(f"  ❌ FL {cat_name}: HTTP {resp.status_code}")
        time.sleep(0.3)


if __name__ == "__main__":
    test_1_no_store_state_fingerprint()
    test_2_wv_batch_codes_coa()
    test_3_fl_store_on_az_state()
    test_4_ga_all_products()
    test_5_fl_sanity_check()
    
    print("\n\n✅ Deep-dive investigation complete!")
