# Changelog

All notable changes to Terprint Menu Downloader are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [2026-03-08]

### Added
- Stock Browse API: cannabinoid fields (thc_percent, cbd_percent, cbg_percent, total_terpene_percent) in response
- Stock Browse API: THC% sort support (sort_by=thc_percent)

### Fixed
- Stock Indexer: SQL enrichment rewrite to match actual Batch table schema (terpenes + cannabinoids from batchJSON)
- Stock Indexer: Extract prices from array format for Sanctuary/Sweed POS dispensaries
- Startup: Run stock index build in background (asyncio.create_task) to pass container activation probe

## [2026-02-19]

### Fixed
- Stock API: Move ledger routes before wildcard catch-all routes
- Stock API: Change async def to def on all stock route endpoints to prevent event loop blocking
- Stock API: Prevent 503 on cold-start by pre-warming index cache

### Added
- ADR-006: Stock ledger persistent history

## [2026-02-14]

### Added
- Stock Browse API with strain search and real-time stock checks
- Stock Index Builder  consolidates batch files into queryable stock index
- Batch tracking with COA integration
- 5-stage data pipeline architecture
- Scheduled menu downloads: MUV, Trulieve, Cookies, Flowery, Curaleaf
- Batch creator and COA processor integration
