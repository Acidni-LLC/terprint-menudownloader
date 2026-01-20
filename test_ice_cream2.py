import json
import re

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

products = data.get('products', {}).get('list', [])

# Check Ice Cream Candy
for p in products:
    name = p.get('name', '').split(' - ')[0].strip()
    if name == 'Ice Cream Candy':
        desc = p.get('description', '')
        
        pattern1 = r\"lineage:\s*([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n]|$)\"
        pattern2 = r'cross of\s+([A-Za-z0-9#\s&\']+?)\s+and\s+([A-Za-z0-9#\s&\']+?)(?:\.|\n|$)'
        
        m1 = re.search(pattern1, desc, re.IGNORECASE)
        m2 = re.search(pattern2, desc, re.IGNORECASE)
        
        print(f'Ice Cream Candy description (looking for x patterns):')
        print(f'  Pattern 1 match: {m1.groups() if m1 else \"NO MATCH\"}')
        print(f'  Pattern 2 match: {m2.groups() if m2 else \"NO MATCH\"}')
        
        # Show all x occurrences
        all_x = re.findall(r'([A-Za-z0-9#\s]{5,25})\s*[xX]\s*([A-Za-z0-9#\s]{5,25})', desc)
        print(f'\n  All \" x \" patterns in text:')
        for i, (p1, p2) in enumerate(all_x, 1):
            print(f'    {i}. {p1.strip()} x {p2.strip()}')
        break
