import sys
sys.path.insert(0, "src")
from terprint_menu_downloader.genetics.scraper import GeneticsScraper

scraper = GeneticsScraper()

# Ice Cream Candy description
desc = """Reserve Flower encompasses an array of premium cannabis genetics. These exotic strains have been rigorously phenohunted in the MÜV Cultivation and present striking features: dense trichome production, unique bud structures, and robust THC content.

Ice Cream Candy is sure to satisfy your sweet tooth! Float away with Ice Cream Candy. This hybrid cross of Dolato x Slurricane 23 is both calming and stimulating."""

result = scraper._extract_lineage_from_text(desc)
print(f"Result: {result}")

# Now test with just the lineage portion
lineage_text = "hybrid cross of Dolato x Slurricane 23"
result2 = scraper._extract_lineage_from_text(lineage_text)
print(f"Result with lineage text: {result2}")

# And just "Dolato x Slurricane 23"
just_parents = "Dolato x Slurricane 23"
result3 = scraper._parse_lineage(just_parents)
print(f"Result with _parse_lineage: {result3}")
