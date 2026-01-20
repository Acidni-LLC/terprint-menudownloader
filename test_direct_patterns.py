import re

desc = """Reserve Flower encompasses an array of premium cannabis genetics. These exotic strains have been rigorously phenohunted in the MÜV Cultivation and present striking features: dense trichome production, unique bud structures, and robust THC content.

Ice Cream Candy is sure to satisfy your sweet tooth! Float away with Ice Cream Candy. This hybrid cross of Dolato x Slurricane 23 is both calming and stimulating."""

patterns = [
    r"lineage:\s*([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n]|$)",
    r"cross of\s+([A-Za-z0-9#\s&']+?)\s+and\s+([A-Za-z0-9#\s&']+?)(?:\.|\n|$)",
]

for i, p in enumerate(patterns, 1):
    match = re.search(p, desc, re.IGNORECASE | re.MULTILINE)
    if match:
        print(f"Pattern {i} MATCHED:")
        print(f"  Groups: {match.groups()}")
        print(f"  Full match: {match.group(0)}")
    else:
        print(f"Pattern {i}: No match")
