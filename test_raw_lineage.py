import json
import re

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])

print('=== ALL LINEAGE FIELDS (RAW) ===\n')
for p in products:
    desc = p.get('description', '')
    name = p.get('name', 'N/A')
    
    # Look for lineage
    if 'lineage:' in desc.lower():
        # Extract everything from Lineage: to next section/newline
        match = re.search(r'lineage:\s*([^\n]+)', desc, re.IGNORECASE)
        if match:
            lineage_text = match.group(1).strip()
            print(f'{name:30} | {lineage_text}')
