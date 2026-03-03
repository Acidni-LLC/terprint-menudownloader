"""Final clarifying test: store_id vs state_name as data selector"""
import requests, json, time

BASE_URL = "https://www.trulieve.com/api/graphql"
HEADERS = {
    "accept": "*/*",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0",
    "x-pylot-backend": "trulieve_prod",
    "x-pylot-query": "products",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "referer": "https://www.trulieve.com/category/flower",
}
QUERY = 'query products($searchCriteria:[SearchCriteriaInput!]!,$pageSize:Int=50,$currentPage:Int=1,$sort:ProductAttributeSortInput={}){products(searchCriteria:$searchCriteria pageSize:$pageSize currentPage:$currentPage sort:$sort){items{id name sku categories{name}} page_info{total_pages} total_count}}'

def test(state, store, label):
    cookies = f"trulieve_fe_url=true; trulieve_fe_cluster=live; state_name={state}; checkouttype=pickup; store_id={store}"
    h = HEADERS.copy()
    h["cookie"] = cookies
    h["store"] = store
    v = json.dumps({"currentPage":1,"pageSize":3,"searchCriteria":[{"attribute_code":"category_uid","filter_action":"EQ","filter_value":"MjA4"}],"sort":{}})
    r = requests.get(BASE_URL, headers=h, params={"query":QUERY,"operationName":"products","variables":v}, timeout=15)
    total = 0
    sample = ""
    if r.status_code == 200:
        d = r.json().get("data",{}).get("products")
        if d:
            total = d.get("total_count",0)
            items = d.get("items",[])
            if items:
                sample = items[0].get("name","")[:40]
    s = "OK" if r.status_code == 200 and total > 0 else "EMPTY" if r.status_code == 200 else f"HTTP {r.status_code}"
    print(f"  {label:55s} -> {s:8s} | {total:3d} products | {sample}")
    time.sleep(0.3)

print("KEY TEST: Does store_id or state_name select the data?")
print("=" * 95)
print("\nCross-state store mixing:")
for state, store in [("FL","palm_coast"), ("WV","morgantown"), ("FL","morgantown"), ("WV","palm_coast")]:
    test(state, store, f"state={state} store={store}")

print("\nAZ slug variants from website URL patterns:")
# Website shows /dispensaries/arizona/apache-junction
az_slugs = ["az-apache-junction", "arizona-apache-junction", "az_apache_junction",
            "apache_junction_az", "AZ-Apache-Junction", "apache-junction-az"]
for slug in az_slugs:
    test("AZ", slug, f"AZ + {slug}")

print("\nPA slug variants:")
pa_slugs = ["pa-camp-hill", "pennsylvania-camp-hill", "pa_camp_hill", "camp-hill-pa"]
for slug in pa_slugs:
    test("PA", slug, f"PA + {slug}")

# The pattern we see: FL stores use underscores (palm_coast), WV stores also use
# underscores (morgantown). AZ stores ALL fail with 550.
# Maybe AZ/PA/MD/CT/CA use a DIFFERENT Magento instance entirely?

print("\nTesting if the 550 is a Magento store view issue:")
# Magento GraphQL requires the 'store' header to match a configured store view
# Maybe AZ uses a different store view code format
for store_header in ["az", "arizona", "trulieve_az", "trulieve-az", "default_az"]:
    cookies = f"trulieve_fe_url=true; trulieve_fe_cluster=live; state_name=AZ; checkouttype=pickup; store_id=avondale"
    h = HEADERS.copy()
    h["cookie"] = cookies
    h["store"] = store_header  # This is the Magento store view code!
    v = json.dumps({"currentPage":1,"pageSize":3,"searchCriteria":[{"attribute_code":"category_uid","filter_action":"EQ","filter_value":"MjA4"}],"sort":{}})
    r = requests.get(BASE_URL, headers=h, params={"query":QUERY,"operationName":"products","variables":v}, timeout=15)
    total = 0
    if r.status_code == 200:
        try:
            total = r.json().get("data",{}).get("products",{}).get("total_count",0)
        except: pass
    s = "OK" if r.status_code == 200 and total > 0 else "EMPTY" if r.status_code == 200 else f"HTTP {r.status_code}"
    print(f"  AZ store_header='{store_header}' -> {s} | {total} products")
    time.sleep(0.3)

# Try without the 'store' header at all for AZ
print("\nAZ without 'store' header but WITH store_id cookie:")
cookies = "trulieve_fe_url=true; trulieve_fe_cluster=live; state_name=AZ; checkouttype=pickup; store_id=avondale"
h = HEADERS.copy()
h["cookie"] = cookies
# No h["store"] header
v = json.dumps({"currentPage":1,"pageSize":3,"searchCriteria":[{"attribute_code":"category_uid","filter_action":"EQ","filter_value":"MjA4"}],"sort":{}})
r = requests.get(BASE_URL, headers=h, params={"query":QUERY,"operationName":"products","variables":v}, timeout=15)
total = 0
if r.status_code == 200:
    try:
        total = r.json().get("data",{}).get("products",{}).get("total_count",0)
    except: pass
s = "OK" if r.status_code == 200 and total > 0 else "EMPTY" if r.status_code == 200 else f"HTTP {r.status_code}"
print(f"  AZ no store header, store_id cookie=avondale -> {s} | {total} products")
time.sleep(0.3)

# Try with store_id cookie but different from store header
print("\nAZ: store_id=avondale in cookie, store=palm_coast in header:")
cookies = "trulieve_fe_url=true; trulieve_fe_cluster=live; state_name=AZ; checkouttype=pickup; store_id=avondale"
h = HEADERS.copy()
h["cookie"] = cookies
h["store"] = "palm_coast"  # FL store in header, AZ store in cookie
v = json.dumps({"currentPage":1,"pageSize":3,"searchCriteria":[{"attribute_code":"category_uid","filter_action":"EQ","filter_value":"MjA4"}],"sort":{}})
r = requests.get(BASE_URL, headers=h, params={"query":QUERY,"operationName":"products","variables":v}, timeout=15)
total = 0
if r.status_code == 200:
    try:
        total = r.json().get("data",{}).get("products",{}).get("total_count",0)
    except: pass
s = "OK" if r.status_code == 200 and total > 0 else "EMPTY" if r.status_code == 200 else f"HTTP {r.status_code}"
print(f"  AZ cookie store_id=avondale + FL header store=palm_coast -> {s} | {total} products")

print("\n\nDone!")
