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
    # Check if extraction looks clean (no verbs in parent names)
    bad_words = ['is', 'provides', 'offers', 'delivers', 'expect', 'mixed', 'calming', 'stimulating']
    quality = 'CLEAN' if not any(word in p1.lower() or word in p2.lower() for word in bad_words) else ' CHECK'
    print(f'  {quality} {name:28} {p1} x {p2}')

print(f'\nCoverage: {len(unique_genetics)}/54 products = {len(unique_genetics)/54*100:.1f}%')
