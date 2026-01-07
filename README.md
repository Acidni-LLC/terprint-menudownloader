# Terprint Menu Downloader

A Python-based dispensary menu data collection and stock checking system for Florida medical marijuana dispensaries.

## Overview

This project provides:

1. **Scheduled Menu Downloads** - Collects product/menu data from multiple dispensaries (MÜV, Trulieve, Cookies, Flowery) and uploads to Azure Data Lake
2. **Stock API** - REST API for strain search and real-time stock checks
3. **Batch Tracking** - Extracts and tracks batch/lot codes from product data
4. **COA Integration** - Supports Certificate of Analysis (COA) lookups via batch codes

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Azure Function App                           │
│              (terprint-menu-downloader.azurewebsites.net)           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Timer Trigger (7x daily)          HTTP Triggers                    │
│   ┌────────────────────┐            ┌──────────────────────────┐    │
│   │  Menu Downloader   │            │  /api/stock/search       │    │
│   │  - MÜV (86 stores) │            │  /api/stock/{disp}/{id}  │    │
│   │  - Trulieve (162)  │            │  /api/stock/build-index  │    │
│   │  - Cookies (18)    │            │  /api/run                │    │
│   │  - Flowery (15+)   │            │  /api/status             │    │
│   └────────┬───────────┘            └────────────┬─────────────┘    │
│            │                                      │                  │
│            ▼                                      ▼                  │
│   ┌────────────────────┐            ┌──────────────────────────┐    │
│   │  Azure Data Lake   │◄──────────►│    Strain Index          │    │
│   │  (JSON files)      │            │  (strain_index.json)     │    │
│   └────────────────────┘            └──────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Supported Dispensaries

| Dispensary | Stores | Categories | Data Source |
|------------|--------|------------|-------------|
| **MÜV** | 86 | Flower, Concentrates, Vapes, Edibles | REST API |
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
├── azure_function/          # Azure Function App (deployed)
│   ├── function_app.py      # Main function with all HTTP/timer triggers
│   └── requirements.txt     # Function dependencies
│
├── src/terprint_menu_downloader/   # Main package
│   ├── orchestrator.py      # DispensaryOrchestrator - coordinates downloads
│   ├── downloaders/         # Per-dispensary download logic
│   │   ├── muv_downloader.py
│   │   ├── trulieve_downloader.py
│   │   ├── cookies_downloader.py
│   │   └── flowery_downloader.py
│   ├── menus/               # Menu parsing and config
│   │   ├── menu_config.json # Category IDs, store lists, settings
│   │   └── trulieve_fixed.py
│   └── storage/             # Azure Data Lake client
│       └── datalake.py
│
├── docs/                    # Documentation
│   ├── STOCK_API.md         # Full API documentation
│   └── HEALTH_DASHBOARD.md  # Monitoring guide
│
└── menu_downloader.py       # CLI entry point
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
