import json

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])
print(f'Number of products in list: {len(products)}')

if products:
    print(f'\nFirst product keys: {list(products[0].keys())}')
    
    # Find one with lineage
    for p in products[:30]:
        desc = p.get('description', '')
        if 'lineage' in desc.lower():
            print('\n--- PRODUCT WITH LINEAGE ---')
            print('Name:', p.get('name', 'N/A'))
            print('Description:', desc)
            break
