import json

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])

# Check specific products
check_names = ['Ice Cream Candy', 'Pineapple Wino', 'Applescotti']
for p in products:
    name = p.get('name', '').split(' - ')[0].strip()
    if name in check_names:
        desc = p.get('description', '')
        print(f'=== {name} ===')
        # Find lineage portion
        if 'lineage:' in desc.lower():
            idx = desc.lower().index('lineage:')
            print(desc[idx:idx+150])
        else:
            print('No Lineage: field')
        print()
