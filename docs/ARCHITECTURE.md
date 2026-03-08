# Terprint Menu Downloader  Architecture

**Last Updated:** 2026-03-08

## Overview

The Menu Downloader is a Python container app that runs as a background scheduler, collecting dispensary menu data and serving a Stock Browse API. It is the data source for the Stock Explorer in Terprint AI (Teams).

## System Context

`	ext
+-----------------------+     +---------------------------+     +------------------+
| Dispensary APIs       |     | Menu Downloader           |     | Azure SQL        |
| (MUV, Trulieve,      | --> | (ca-terprint-             | --> | (acidni-sql /    |
|  Cookies, Flowery)    |     |  menudownloader)          |     |  terprint DB)    |
+-----------------------+     +---------------------------+     +------------------+
                                      |           |
                                      v           v
                              +-------------+  +-----------+
                              | Blob Storage|  | APIM      |
                              | (stock-     |  | (/menus/) |
                              |  index/)    |  +-----------+
                              +-------------+       |
                                                    v
                                            +---------------+
                                            | Terprint AI   |
                                            | (Teams Tab)   |
                                            +---------------+
`

## Components

### container_app/main.py
FastAPI application entry point. Runs in `scheduler` mode:
- APScheduler triggers menu downloads every 2 hours (8am-10pm EST)
- Stock index build runs on startup (background task)
- Mounts Stock Browse API routes

### container_app/stock_indexer.py
Builds the stock index from dispensary menu files in Blob Storage:
1. Scans all dispensary menu JSONs from today (fallback to yesterday)
2. Enriches items with terpene/cannabinoid data from SQL Batch table
3. Cross-references genetics index for strain type/lineage
4. Applies store location data from dispensary_locations.json
5. Uploads index to Blob: `stock-index/current.json`

### container_app/stock_routes.py
FastAPI router serving the Stock Browse API:
- `GET /api/stock/browse`  paginated search with filters (strain, dispensary, product type, price, THC% sort)
- `GET /api/stock/search`  legacy search endpoint
- `GET /api/stock/ledger/`  persistent event history endpoints

### container_app/notifications.py
Notification service for stock alerts.

### container_app/stock_alerts.py
Stock alert processing triggered by inventory changes.

## Data Flow

`	ext
Dispensary APIs (every 2hrs)
  --> Raw menu JSONs saved to Blob: dispensaries/{dispensary}/{date}/*.json
    --> Batch Creator (POST ca-terprint-batches/api/create-batches)
      --> consolidated_batches_YYYYMMDD.json
        --> COA Processor (POST ca-terprint-batchprocessor/api/run-batch-processor)
          --> SQL enrichment (Batch table: terpenes, cannabinoids)
            --> Stock Index Build (stock-index/current.json)
`

## Infrastructure

| Resource | Value |
|----------|-------|
| Container App | `ca-terprint-menudownloader` |
| Resource Group | `rg-dev-acidni-shared` |
| FQDN | `ca-terprint-menudownloader.greenbay-731aa80e.eastus2.azurecontainerapps.io` |
| APIM Base Path | `/menus` |
| Blob Storage | `stterprintsharedgen2/jsonfiles` |
| SQL Database | `acidni-sql.database.windows.net / terprint` |
| Registry | `cracidnidev.azurecr.io` |

## Security

- SQL password via Key Vault secret reference (`sql-password`)
- Blob access via DefaultAzureCredential (managed identity)
- APIM subscription key required for API access
- Internal ingress with IP restriction (APIM gateway only)

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Health check |
| GET | /api/stock/browse | APIM | Paginated stock search with filters |
| GET | /api/stock/search | APIM | Legacy search |
| POST | /run | APIM | Trigger manual download |
| POST | /build-stock-index | APIM | Trigger manual index build |
| GET | /api/stock/ledger/strain/{slug} | APIM | Strain event history |
| GET | /api/stock/ledger/recent | APIM | Recent stock events |
