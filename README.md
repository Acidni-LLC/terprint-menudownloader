# Terprint Menu Downloader

A Python-based dispensary menu data collection and stock checking system for Florida medical marijuana dispensaries.

## Overview

This project provides:

1. **Scheduled Menu Downloads** - Collects product/menu data from multiple dispensaries (MÃœV, Trulieve, Cookies, Flowery) and uploads to Azure Data Lake
2. **Stock API** - REST API for strain search and real-time stock checks
3. **Batch Tracking** - Extracts and tracks batch/lot codes from product data
4. **COA Integration** - Supports Certificate of Analysis (COA) lookups via batch codes

## Architecture

**5-Stage Data Pipeline:**

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         Terprint Menu Downloader                              â”‚
â”‚            (ca-terprint-menudownloader.greenbay-731aa80e.eastus2...)         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                               â”‚
â”‚   Stage 2: Menu Downloads (Every 2hrs, 8am-10pm EST)                        â”‚
â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                   â”‚
â”‚   â”‚  Scheduled Timer (APScheduler)                      â”‚                   â”‚
â”‚   â”‚  - MÃœV (86 stores)                                  â”‚                   â”‚
â”‚   â”‚  - Trulieve (162 stores Ã— 4 categories)            â”‚                   â”‚
â”‚   â”‚  - Cookies (18 stores)                              â”‚                   â”‚
â”‚   â”‚  - Flowery (16 locations)                           â”‚                   â”‚
â”‚   â”‚  - Curaleaf (45-60 stores)                          â”‚                   â”‚
â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                   â”‚
â”‚                  â”‚ Raw menu JSONs saved to:                                  â”‚
â”‚                  â”‚ dispensaries/{dispensary}/{year}/{month}/{day}/*.json     â”‚
â”‚                  â–¼                                                            â”‚
â”‚   Stage 2.5: Batch Creator (Triggered after downloads)                      â”‚
â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                   â”‚
â”‚   â”‚  POST ca-terprint-batches/api/create-batches       â”‚                   â”‚
â”‚   â”‚  Consolidates all menu files into batch file:      â”‚                   â”‚
â”‚   â”‚  batches/consolidated_batches_YYYYMMDD.json        â”‚                   â”‚
â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                   â”‚
â”‚                  â”‚ Automatically triggers â†“                                  â”‚
â”‚                  â–¼                                                            â”‚
â”‚   Stage 3: COA Processor (Triggered by Batch Creator)                       â”‚
â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                   â”‚
â”‚   â”‚  ca-terprint-batchprocessor/api/run-batch-processorâ”‚                   â”‚
â”‚   â”‚  Extracts batch codes, fetches COAs, writes to SQL  â”‚                   â”‚
â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                   â”‚
â”‚                  â”‚                                                            â”‚
â”‚                  â–¼                                                            â”‚
â”‚   Stock Index Build (After batch creation)                                  â”‚
â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                   â”‚
â”‚   â”‚  StockIndexer.build_index_from_latest()            â”‚                   â”‚
â”‚   â”‚  Reads consolidated batch files + fills missing    â”‚                   â”‚
â”‚   â”‚  dispensaries from raw menus                        â”‚                   â”‚
â”‚   â”‚  Output: stock-index/current.json                   â”‚                   â”‚
â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                   â”‚
â”‚                                                                               â”‚
â”‚   HTTP Triggers (Available via APIM)                                        â”‚
â”‚   â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚   â”‚  Download Controls               â”‚  Stock API                        â”‚   â”‚
â”‚   â”‚  - POST /run (manual trigger)    â”‚  - GET /api/stock/status         â”‚   â”‚
â”‚   â”‚  - GET /status                   â”‚  - GET /api/stock/search?strain= â”‚   â”‚
â”‚   â”‚  - GET /health                   â”‚  - GET /api/stock/{dispensary}   â”‚   â”‚
â”‚   â”‚  - POST /build-stock-index       â”‚  - GET /api/stock/{disp}/{batch} â”‚   â”‚
â”‚   â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â”‚                                                                               â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                    â”‚
                                    â–¼
                    Azure Data Lake Storage Gen2
                    (stterprintsharedgen2/jsonfiles)
                    â”œâ”€â”€ dispensaries/            (Stage 2 output)
                    â”œâ”€â”€ batches/                 (Stage 2.5 output)
                    â””â”€â”€ stock-index/             (Stock index files)
```

**Pipeline Flow:**
1. **Stage 2 (Download)**: Menu Downloader runs every 2 hours â†’ Saves raw JSON files
2. **Stage 2.5 (Batch Creator)**: Auto-triggered after downloads â†’ Creates `consolidated_batches_YYYYMMDD.json`
3. **Stage 3 (COA Processor)**: Auto-triggered by Batch Creator â†’ Extracts batch codes, fetches COAs, writes to SQL
4. **Stock Index Build**: Auto-triggered after batch creation â†’ Builds searchable index from consolidated batches + raw menus

**APIM Integration:**
- Base URL: `https://api.acidni.net/menus`
- All stock endpoints available through APIM gateway
- See [openapi.json](./openapi.json) for complete API spec

## Supported Dispensaries

| Dispensary | Stores | Categories | Data Source |
|------------|--------|------------|-------------|
| **MÃœV** | 86 | Flower, Concentrates, Vapes, Edibles | REST API |
| **Trulieve** | 162 | Flower, Pre-rolls, Concentrates, Vapes | GraphQL |
| **Cookies** | 18 | All categories | Dutchie API |
| **Flowery** | 15+ | All categories | Custom API |

## Download Schedule

Menu downloads run automatically at these times (UTC):
- `0:00, 2:00, 14:00, 16:00, 18:00, 20:00, 22:00`

This translates to EST (during Eastern Standard Time):
- **7:00 PM, 9:00 PM, 9:00 AM, 11:00 AM, 1:00 PM, 3:00 PM, 5:00 PM**

## Stock API

Full API documentation: [docs/STOCK_API.md](docs/STOCK_API.md)

### Quick Examples

**Search for a strain:**
```bash
curl "https://terprint-menu-downloader.azurewebsites.net/api/stock/search?strain=Gelato&code=YOUR_KEY"
```

**Check specific batch stock:**
```bash
curl "https://terprint-menu-downloader.azurewebsites.net/api/stock/trulieve/70489_0007770955?code=YOUR_KEY"
```

### Important: Batch IDs vs Strain Names

- **Strain Search** (`/api/stock/search`) - Finds products by strain name across all current inventory. This is the recommended method for finding available stock.

- **Batch Stock Check** (`/api/stock/{dispensary}/{batch_id}`) - Checks if a *specific* batch ID is currently in stock. Batch IDs are tied to production runs and may no longer exist in current inventory.

If a batch check returns "Out of Stock" or "Checked 0 stores", the API will suggest searching by strain name instead.

## Local Development

### Prerequisites

- Python 3.10+
- Azure CLI (for deployment)
- Access to Azure Data Lake (stterprintsharedgen2)

### Setup

```powershell
# Clone the repo
git clone https://github.com/Acidni-LLC/terprint-menu-downloader.git
cd terprint-menu-downloader

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .

# Set environment variables (or use .env file)
$env:AZURE_STORAGE_ACCOUNT = "stterprintsharedgen2"
```

### Run Menu Download Locally

```powershell
# Full download (all dispensaries)
python menu_downloader.py

# Single dispensary test
python menu_downloader.py --dispensary trulieve --dev-mode

# Dry run (no Azure upload)
python menu_downloader.py --dry-run
```

### Run Azure Function Locally

```powershell
cd azure_function
func start
```

## Project Structure

```
â”œâ”€â”€ azure_function/          # Azure Function App (deployed)
â”‚   â”œâ”€â”€ function_app.py      # Main function with all HTTP/timer triggers
â”‚   â””â”€â”€ requirements.txt     # Function dependencies
â”‚
â”œâ”€â”€ src/terprint_menu_downloader/   # Main package
â”‚   â”œâ”€â”€ orchestrator.py      # DispensaryOrchestrator - coordinates downloads
â”‚   â”œâ”€â”€ downloaders/         # Per-dispensary download logic
â”‚   â”‚   â”œâ”€â”€ muv_downloader.py
â”‚   â”‚   â”œâ”€â”€ trulieve_downloader.py
â”‚   â”‚   â”œâ”€â”€ cookies_downloader.py
â”‚   â”‚   â””â”€â”€ flowery_downloader.py
â”‚   â”œâ”€â”€ menus/               # Menu parsing and config
â”‚   â”‚   â”œâ”€â”€ menu_config.json # Category IDs, store lists, settings
â”‚   â”‚   â””â”€â”€ trulieve_fixed.py
â”‚   â””â”€â”€ storage/             # Azure Data Lake client
â”‚       â””â”€â”€ datalake.py
â”‚
â”œâ”€â”€ docs/                    # Documentation
â”‚   â”œâ”€â”€ STOCK_API.md         # Full API documentation
â”‚   â””â”€â”€ HEALTH_DASHBOARD.md  # Monitoring guide
â”‚
â””â”€â”€ menu_downloader.py       # CLI entry point
```

## Configuration

Main configuration is in `src/terprint_menu_downloader/menus/menu_config.json`:

```json
{
  "trulieve_settings": {
    "category_ids": ["MjA4", "MjM3", "MjA5", "Ng=="],
    "store_ids_csv": "trulieve_stores.csv"
  },
  "download_settings": {
    "max_workers": 8,
    "request_timeout": 30
  }
}
```

### Trulieve Category IDs

| Category | Base64 ID | Decoded |
|----------|-----------|---------|
| Flower | `MjA4` | 208 |
| Pre-rolls | `MjM3` | 237 |
| Concentrates | `MjA5` | 209 |
| Vapes | `Ng==` | 6 |

## Deployment

### Deploy Azure Function

```powershell
# Using Azure CLI
az login
az functionapp deployment source config-zip \
  -g rg-terprint-shared \
  -n terprint-menu-downloader \
  --src azure_function.zip

# Or using the deployment script
.\deploy-azure-function.ps1
```

### Environment Variables (Azure Function)

| Variable | Description |
|----------|-------------|
| `AZURE_STORAGE_ACCOUNT` | Storage account name |
| `AZURE_STORAGE_CONTAINER` | Blob container (default: jsonfiles) |
| `BATCH_PROCESSOR_URL` | URL to batch processor function |

## Monitoring

- **Azure Function Logs**: Application Insights
- **Health Dashboard**: [docs/HEALTH_DASHBOARD.md](docs/HEALTH_DASHBOARD.md)
- **Job Tracking**: Cosmos DB (terprint-menu-downloader database)

## Related Projects

- **terprint.acidni.net** - Web frontend that uses this API
- **Terprint.Python** - Shared Python utilities (logging, config)
- **terprint-config** - Centralized configuration package

## Changelog

| Date | Changes |
|------|---------|
| 2025-12-16 | Added Trulieve Concentrates category (MjA5) |
| 2025-12-16 | Added suggestion field to stock check for out-of-stock batches |
| 2025-12-15 | Stock API v1.0 deployed |

## License

Proprietary - Acidni LLC
