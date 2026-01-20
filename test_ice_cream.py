import json
import re
import sys
sys.path.insert(0, 'src')

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])

# Find the bad extraction
for p in products:
    name = p.get('name', '').split(' - ')[0].strip()
    if name == 'Ice Cream Candy':
        desc = p.get('description', '')
        print(f'=== {name} ===\n')
        print(f'Full description (last 300 chars):\n{desc[-300:]}\n')
        
        # Test patterns
        pattern1 = r"lineage:\s*([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n]|$)"
        pattern2 = r"(?:cross of|crossed? with)\s+([A-Za-z0-9#\s&']+?)\s+(?:and|[xX])\s+([A-Za-z0-9#\s&']+?)(?:[,.\n]|$)"
        
        match1 = re.search(pattern1, desc, re.IGNORECASE)
        match2 = re.search(pattern2, desc, re.IGNORECASE)
        
        if match1:
            print(f'Pattern 1 (Lineage:) MATCHED:')
            print(f'  Groups: {match1.groups()}')
        if match2:
            print(f'Pattern 2 (crossed with) MATCHED:')
            print(f'  Groups: {match2.groups()}')
        break
