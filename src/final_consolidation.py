import json
from datetime import datetime

# Load original 42 strains
with open("all_genetics_20260120.json", "r") as f:
    original = json.load(f)

# Load 45 from menu descriptions
with open("menu_description_genetics_20260120_045406.json", "r") as f:
    menu_desc = json.load(f)

orig_strains = original.get("strains", [])
desc_genetics = menu_desc.get("genetics", [])

print(f" Original (Menu JSON): {len(orig_strains)} strains")
print(f" Menu Descriptions: {len(desc_genetics)} genetics\n")

# Merge and deduplicate
all_genetics = {}

# Add original strains
for s in orig_strains:
    strain_name = s.get("name", s.get("strain_name", ""))
    if strain_name:
        all_genetics[strain_name] = {
            "strain_name": strain_name,
            "parent1": s.get("parent1", s.get("parent_1", "")),
            "parent2": s.get("parent2", s.get("parent_2", "")),
            "dispensary": s.get("dispensary", "Multiple"),
            "source": "Menu JSON Extraction",
            "confidence": "Medium"
        }

# Add menu description genetics
for g in desc_genetics:
    strain_name = g["strain_name"]
    if strain_name not in all_genetics:
        all_genetics[strain_name] = {
            "strain_name": strain_name,
            "parent1": g.get("parent1", ""),
            "parent2": g.get("parent2", ""),
            "dispensary": g.get("dispensary", "Unknown"),
            "source": "Menu Description Parsing",
            "confidence": "High"
        }

consolidated = list(all_genetics.values())
print(f" Total Unique Strains: {len(consolidated)}\n")

# Generate SQL
sql_lines = [
    f"-- TERPRINT GENETICS IMPORT",
    f"-- Generated: {datetime.now().isoformat()}",
    f"-- Total Strains: {len(consolidated)}",
    f"-- Sources: Menu JSON Extraction + Menu Description Parsing",
    "",
    "-- Create table if not exists",
    "IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Genetics')",
    "BEGIN",
    "    CREATE TABLE Genetics (",
    "        Id INT IDENTITY(1,1) PRIMARY KEY,",
    "        StrainName NVARCHAR(255) NOT NULL,",
    "        Parent1 NVARCHAR(255),",
    "        Parent2 NVARCHAR(255),",
    "        Dispensary NVARCHAR(100),",
    "        Source NVARCHAR(100),",
    "        Confidence NVARCHAR(50),",
    "        CreatedDate DATETIME DEFAULT GETDATE(),",
    "        CONSTRAINT UQ_StrainName UNIQUE(StrainName)",
    "    )",
    "END",
    "GO",
    "",
]

for g in sorted(consolidated, key=lambda x: x["strain_name"]):
    strain = g["strain_name"].replace("'", "''")
    parent1 = g["parent1"].replace("'", "''") if g["parent1"] else "NULL"
    parent2 = g["parent2"].replace("'", "''") if g["parent2"] else "NULL"
    dispensary = g["dispensary"].replace("'", "''")
    source = g["source"].replace("'", "''")
    confidence = g.get("confidence", "Medium")
    
    if parent1 != "NULL":
        parent1 = f"'{parent1}'"
    if parent2 != "NULL":
        parent2 = f"'{parent2}'"
    
    sql_lines.append(
        f"INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) "
        f"SELECT '{strain}', {parent1}, {parent2}, '{dispensary}', '{source}', '{confidence}' "
        f"WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = '{strain}');"
    )

sql_lines.extend([
    "",
    "-- Verification",
    "SELECT COUNT(*) AS TotalGenetics FROM Genetics;",
    "SELECT Source, COUNT(*) AS Count FROM Genetics GROUP BY Source ORDER BY Count DESC;",
    "SELECT TOP 20 StrainName, Parent1, Parent2, Dispensary FROM Genetics ORDER BY StrainName;",
])

# Save files
json_file = "FINAL_CONSOLIDATED_GENETICS.json"
sql_file = "FINAL_GENETICS_IMPORT.sql"

with open(json_file, "w") as f:
    json.dump({
        "consolidation_date": datetime.now().isoformat(),
        "total": len(consolidated),
        "genetics": consolidated
    }, f, indent=2)

with open(sql_file, "w", encoding="utf-8") as f:
    f.write("\n".join(sql_lines))

print(f" JSON: {json_file}")
print(f" SQL:  {sql_file}\n")

# Show samples
print(" Sample Genetics (with parents):")
with_parents = [g for g in consolidated if g.get("parent1") and g.get("parent2")]
for g in sorted(with_parents, key=lambda x: x["strain_name"])[:15]:
    print(f"  {g['strain_name']} = {g['parent1']} x {g['parent2']}")

print(f"\n SUCCESS! Ready to import {len(consolidated)} strain genetics to database!")
