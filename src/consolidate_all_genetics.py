"""
Consolidate genetics from all sources:
1. Original 42 from menu JSON extraction
2. 45 from menu descriptions (MÜV + Cookies)
3. Future: COA parsing, web scraping, manual entry
"""
import json
from datetime import datetime


def load_original_genetics():
    """Load the original 42 genetics."""
    try:
        with open('../all_genetics_20260120_031359.json', 'r') as f:
            data = json.load(f)
            return data.get('genetics', [])
    except FileNotFoundError:
        print(" Original genetics file not found")
        return []


def load_menu_description_genetics():
    """Load genetics from menu descriptions."""
    try:
        import glob
        files = glob.glob('menu_description_genetics_*.json')
        if files:
            with open(sorted(files)[-1], 'r') as f:  # Most recent
                data = json.load(f)
                return data.get('genetics', [])
    except Exception as e:
        print(f" Error loading menu description genetics: {e}")
    return []


def merge_genetics(sources):
    """Merge genetics from multiple sources, deduplicating by strain name."""
    merged = {}
    stats = {'total': 0, 'by_source': {}}
    
    for source_name, genetics_list in sources.items():
        stats['by_source'][source_name] = len(genetics_list)
        stats['total'] += len(genetics_list)
        
        for g in genetics_list:
            strain_name = g.get('strain_name', '').strip()
            if not strain_name:
                continue
            
            # Use first occurrence (or prefer higher confidence)
            if strain_name not in merged:
                merged[strain_name] = {
                    'strain_name': strain_name,
                    'parent1': g.get('parent1', ''),
                    'parent2': g.get('parent2', ''),
                    'dispensary': g.get('dispensary', 'Unknown'),
                    'source': source_name,
                    'confidence': g.get('confidence', 'Medium'),
                }
    
    stats['unique'] = len(merged)
    stats['duplicates'] = stats['total'] - stats['unique']
    
    return list(merged.values()), stats


def generate_sql_import(genetics):
    """Generate SQL INSERT statements."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    sql_lines = [
        f"-- Genetics Import - {len(genetics)} strains",
        f"-- Generated: {datetime.now().isoformat()}",
        f"-- Sources: Menu JSON + Menu Descriptions (MÜV, Cookies)",
        "",
        "-- Check if table exists (create if needed)",
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
        "-- Insert genetics (with duplicate handling)",
    ]
    
    for g in sorted(genetics, key=lambda x: x['strain_name']):
        strain = g['strain_name'].replace("'", "''")
        parent1 = g['parent1'].replace("'", "''") if g['parent1'] else 'NULL'
        parent2 = g['parent2'].replace("'", "''") if g['parent2'] else 'NULL'
        dispensary = g['dispensary'].replace("'", "''")
        source = g['source'].replace("'", "''")
        confidence = g.get('confidence', 'Medium')
        
        if parent1 != 'NULL':
            parent1 = f"'{parent1}'"
        if parent2 != 'NULL':
            parent2 = f"'{parent2}'"
        
        sql_lines.append(
            f"INSERT INTO Genetics (StrainName, Parent1, Parent2, Dispensary, Source, Confidence) "
            f"SELECT '{strain}', {parent1}, {parent2}, '{dispensary}', '{source}', '{confidence}' "
            f"WHERE NOT EXISTS (SELECT 1 FROM Genetics WHERE StrainName = '{strain}');"
        )
    
    sql_lines.append("")
    sql_lines.append("-- Verification query")
    sql_lines.append("SELECT COUNT(*) AS TotalGenetics FROM Genetics;")
    sql_lines.append("SELECT Source, COUNT(*) AS Count FROM Genetics GROUP BY Source;")
    
    filename = f"genetics_import_consolidated_{timestamp}.sql"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(sql_lines))
    
    return filename


if __name__ == "__main__":
    print(" Consolidating genetics from all sources...\n")
    
    # Load all sources
    original = load_original_genetics()
    menu_desc = load_menu_description_genetics()
    
    print(f" Loaded {len(original)} from original extraction")
    print(f" Loaded {len(menu_desc)} from menu descriptions")
    
    # Merge
    sources = {
        'Menu JSON Extraction': original,
        'Menu Description Parsing': menu_desc,
    }
    
    consolidated, stats = merge_genetics(sources)
    
    # Save consolidated JSON
    output = {
        'consolidation_date': datetime.now().isoformat(),
        'stats': stats,
        'sources': list(sources.keys()),
        'genetics': consolidated
    }
    
    json_filename = f"consolidated_genetics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_filename, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Generate SQL
    sql_filename = generate_sql_import(consolidated)
    
    # Print summary
    print(f"\n Consolidation Summary:")
    print(f"  Total records processed: {stats['total']}")
    print(f"  Unique strains: {stats['unique']}")
    print(f"  Duplicates removed: {stats['duplicates']}")
    print(f"\n  By Source:")
    for source, count in stats['by_source'].items():
        print(f"    {source}: {count}")
    
    print(f"\n Output Files:")
    print(f"  JSON: {json_filename}")
    print(f"  SQL:  {sql_filename}")
    
    print(f"\n Ready to import {stats['unique']} unique strain genetics to database!")
    
    # Show sample
    print(f"\n Sample Genetics (first 10):")
    for g in sorted(consolidated, key=lambda x: x['strain_name'])[:10]:
        if g['parent1'] and g['parent2']:
            print(f"  {g['strain_name']} = {g['parent1']} x {g['parent2']} ({g['source']})")
        else:
            print(f"  {g['strain_name']} (parents unknown, {g['source']})")
