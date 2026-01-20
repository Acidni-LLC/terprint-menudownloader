import json
import re

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])

print('=== MÜV LINEAGE TEXT SAMPLES ===\n')
for p in products[:20]:
    desc = p.get('description', '')
    name = p.get('name', 'N/A')
    
    # Look for lineage patterns
    if 'lineage:' in desc.lower():
        # Extract the lineage portion
        lineage_match = re.search(r'lineage:\s*([^\n]+)', desc, re.IGNORECASE)
        if lineage_match:
            print(f'{name:30}  {lineage_match.group(1)[:80]}')
