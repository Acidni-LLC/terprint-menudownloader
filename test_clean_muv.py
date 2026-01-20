import json
import sys
sys.path.insert(0, 'src')
from terprint_menu_downloader.genetics.scraper import GeneticsScraper

with open('muv_menu_latest.json', 'r') as f:
    data = json.load(f)

scraper = GeneticsScraper()
genetics = scraper._extract_muv(data, 'test.json')

# Get unique strains
unique_genetics = {}
for g in genetics:
    if g.strain_name not in unique_genetics:
        unique_genetics[g.strain_name] = (g.parent_1, g.parent_2)

print(f'\nExtracted genetics for {len(unique_genetics)} unique strains\n')
print('Strains with genetics:')
for name in sorted(unique_genetics.keys()):
    p1, p2 = unique_genetics[name]
    print(f'  {name:30} {p1} x {p2}')

print(f'\nCoverage: {len(unique_genetics)}/54 products = {len(unique_genetics)/54*100:.1f}%')
print('Data quality: Only Lineage: prefix extractions (high confidence)')
