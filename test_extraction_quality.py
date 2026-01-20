import json
import sys
sys.path.insert(0, 'src')
from terprint_menu_downloader.genetics.scraper import GeneticsScraper

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

scraper = GeneticsScraper()
genetics = scraper._extract_muv(data, 'test.json')

# Check for specific problem cases
problem_cases = ['Ice Cream Candy', 'Jokerz Candy', 'Mint Diesel', 'Pineapple Wino']
print('=== PROBLEM EXTRACTIONS ===\n')
for g in genetics:
    if g.strain_name in problem_cases:
        print(f'{g.strain_name}: {g.parent_1} x {g.parent_2}')

# Also show what we're missing
products = data.get('products', {}).get('list', [])
extracted_names = set([g.strain_name for g in genetics])
print('\n=== PRODUCTS WITH LINEAGE NOT EXTRACTED ===\n')
for p in products:
    name = p.get('name', '').split(' - ')[0].strip()
    desc = p.get('description', '')
    if 'lineage:' in desc.lower() and name not in extracted_names:
        lineage_start = desc.lower().index('lineage:')
        print(f'{name}: {desc[lineage_start:lineage_start+100]}')
