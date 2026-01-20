import re

text = "hybrid cross of Dolato x Slurricane 23 is both calming"

pattern2 = r"cross of\s+([A-Za-z0-9#\s&']+?)\s+and\s+([A-Za-z0-9#\s&']+?)(?:\.|\n|$)"

match = re.search(pattern2, text, re.IGNORECASE)
print(f"Pattern 2 match: {match}")

# But wait, let me check pattern 1 on this text (shouldn't match since no Lineage:)
pattern1 = r"lineage:\s*([A-Za-z0-9#\s&']+?)\s*[xX]\s*([A-Za-z0-9#\s&']+?)(?:\s*[\(.\n]|$)"
match1 = re.search(pattern1, text, re.IGNORECASE)
print(f"Pattern 1 match: {match1}")

# But the _parse_lineage might be getting called on the partial text
# Let me check what happens if we extract "cross of X" as a single capture
