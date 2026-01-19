# Genetics Scraper Module

Extracts strain genetics/lineage information from cannabis menu data and stores it in CDES-compatible format.

## Features

- Real-time genetics extraction during menu downloads
- Batch processing of historical menu data
- Dispensary-specific extraction logic (Trulieve, Cookies, Curaleaf, MÜV, Flowery)
- CDES v1.0 compatible data format
- Azure Blob Storage integration (partitioned for efficient lookup)
- Compatible with terprint-config GeneticsClient for reading

## Usage

### Extract Genetics from Menu Download

```python
from terprint_menu_downloader.genetics import GeneticsScraper

# Initialize scraper
scraper = GeneticsScraper()

# Extract from real-time menu data
menu_data = {
    "products": [
        {
            "name": "Blue Dream - Flower",
            "strain": "Blue Dream",
            "description": "Lineage: Blueberry x Haze..."
        }
    ]
}

result = scraper.extract_from_menu(menu_data, dispensary="trulieve")

print(f"Found genetics for {result.unique_strains} strains")
for genetics in result.genetics_found:
    print(f"{genetics.strain_name}: {genetics.parent_1} x {genetics.parent_2}")
```

### Save to Azure Blob Storage

```python
import asyncio
from terprint_menu_downloader.genetics import GeneticsStorage

async def save_genetics():
    # Initialize storage
    storage = GeneticsStorage()
    await storage.connect()
    
    # Save genetics (merges with existing data)
    stats = await storage.save_genetics(result.genetics_found)
    
    print(f"Saved: {stats['new']} new, {stats['updated']} updated")
    print(f"Modified partitions: {stats['partitions_modified']}")
    
    # Get stats
    db_stats = await storage.get_stats()
    print(f"Total strains in database: {db_stats['total_strains']}")
    print(f"Strains with lineage: {db_stats['strains_with_lineage']}")

asyncio.run(save_genetics())
```

### Integrate with Menu Downloader Orchestrator

```python
from terprint_menu_downloader.orchestrator import DispensaryOrchestrator
from terprint_menu_downloader.genetics import GeneticsScraper, GeneticsStorage

orchestrator = DispensaryOrchestrator()
scraper = GeneticsScraper()
storage = GeneticsStorage()

menu_data = orchestrator.download_dispensary("trulieve")
result = scraper.extract_from_menu(menu_data, dispensary="trulieve", source_file="menu.json")

async def save():
    await storage.connect()
    stats = await storage.save_genetics(result.genetics_found)
    print(f"Genetics extracted and saved: {stats['new']} new, {stats['updated']} updated")

# asyncio.run(save())
```
```

## Data Models

### StrainGenetics

Main genetics data model compatible with terprint-config:

```python
@dataclass
class StrainGenetics:
    strain_name: str              # "Blue Dream"
    strain_slug: str              # "blue-dream"
    parent_1: Optional[str]       # "Blueberry"
    parent_2: Optional[str]       # "Haze"
    breeder: Optional[str]        # "DJ Short"
    strain_type: Optional[str]    # "hybrid", "indica", "sativa"
    effects: List[str]            # ["relaxing", "uplifting"]
    source_dispensary: str        # "trulieve"
    source_file: str              # "dispensaries/trulieve/2026/01/19/menu.json"
    scraped_at: str               # ISO timestamp
```

### CDESGenetics

CDES v1.0 compatible format for Strain.genetics field:

```python
@dataclass
class CDESGenetics:
    lineage: List[str]            # ["Blueberry", "Haze"]
    breeder: Optional[str]        # "DJ Short"
    cross: Optional[str]          # "Blueberry x Haze"
```

## Storage Structure

Genetics are stored in Azure Blob Storage (`genetics-data` container):

```
genetics-data/
 index/
    strains-index.json      # Quick lookup index
 partitions/
     a.json                  # Strains starting with 'a'
     b.json                  # Strains starting with 'b'
     ...
     z.json
```

This partitioned structure allows:
- Fast lookups (read only 1 partition file)
- Efficient updates (modify only affected partitions)
- Compatibility with `terprint-config` GeneticsClient

## Dispensary Support

- Trulieve: HTML in custom_attributes_product[strain_description]
- Cookies: informations.genetics or description
- Curaleaf: description
- MÜV: description
- Flowery: description fields
- Sunburn: similar to MÜV
- Generic: fallback pattern matching

## Integration with terprint-config

The genetics database is read by `terprint-config` GeneticsClient:

```python
# In any Terprint service (AI Chat, Recommender, etc.)
from terprint_config.genetics import GeneticsClient

client = GeneticsClient()
lineage = client.get_lineage("Blue Dream")
# Returns: ("Blueberry", "Haze")

# Full strain data
strain = client.get_strain("Blue Dream")
# Returns: {...genetics dict...}
```

## Environment Variables

```bash
# Optional - uses DefaultAzureCredential if not provided
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;..."

# Storage account (defaults to stterprintsharedgen2)
GENETICS_STORAGE_ACCOUNT="stterprintsharedgen2"
```

## CLI Tools

```bash
# Install dependencies (Poetry)
poetry add azure-storage-blob azure-identity

# Run genetics extraction on historical data (planned)
python -m terprint_menu_downloader.genetics.cli \
    --dispensary trulieve \
    --days 30 \
    --save
```

## CDES Compatibility

This module produces data compatible with:

- **CDES v1.0 Strain Schema** - `Strain.genetics` field
- **terprint-config v4.6.0** - GeneticsClient can read the data
- **terprint-ai-* services** - Use GeneticsClient for lineage info
- **Azure Event House** - Future: Genetics can be ingested to Event House

### CDES Strain.genetics Format

```json
{
  "$schema": "https://cdes.terprint.com/v1/strain.schema.json",
  "id": "strain_blue-dream_001",
  "name": "Blue Dream",
  "strain_type": "hybrid",
  "genetics": {
    "lineage": ["Blueberry", "Haze"],
    "breeder": "DJ Short",
    "cross": "Blueberry x Haze"
}
```

 

## Next Steps

1. **Integrate with Orchestrator** - Add genetics extraction to download flow
2. **Create CLI Tool** - Batch extract from historical menu data
3. **Add to v2 Endpoints** - Return genetics in CDES v2/strains endpoint
4. **Event House Ingestion** - Load genetics to Event House for analytics
5. **Power BI Integration** - Visualize strain lineage trees

## See Also

- [terprint-config/cannabis-genetics-scraper](https://github.com/Acidni-LLC/terprint-config/tree/main/cannabis-genetics-scraper)
- [terprint-config/genetics.py](https://github.com/Acidni-LLC/terprint-config/blob/main/terprint_config/genetics.py)
- [CDES v1.0 Specification](https://github.com/Acidni-LLC/terprint-config/blob/main/terprint-core/standards/CDES_SPECIFICATION_V1.md)
- [V2_API_GUIDE.md](https://github.com/Acidni-LLC/terprint-config/blob/main/docs/V2_API_GUIDE.md)
