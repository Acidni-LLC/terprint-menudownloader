# Menu Downloader (Data Ingestion) - AI Guidelines

## Project Context

You are working on **Menu Downloader**, the Stage 2 data ingestion component of the Terprint pipeline. Your purpose is to download menu data from Florida dispensary APIs/websites and store raw JSON in Azure Blob Storage.

### Role in Pipeline
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Stage 2: DATA INGESTION (YOU ARE HERE)                                     │
│                                                                             │
│  Menu Explorer → [Menu Downloader] → Blob Storage → COA Data Extractor     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Business Domain
- **Industry**: Cannabis/Medical Marijuana Data Analytics
- **Geography**: Florida dispensaries
- **Data Types**: Strains, batches, terpenes, cannabinoids, COA (Certificate of Analysis)
- **End Users**: Medical marijuana patients, dispensary staff, data analysts, business stakeholders

### System Purpose
1. **Data Aggregation**: Collect menu data from multiple Florida dispensaries
2. **Data Extraction**: Parse and extract batch, strain, terpene, and cannabinoid information
3. **Data Presentation**: Provide searchable strain/terpene data via website
4. **Analytics**: Generate business intelligence reports via Power BI
5. **Marketplace**: Azure Marketplace SaaS offering with metering and subscriptions

### Azure Resources
- **Function App**: `func-terprint-menudownloader`
- **Resource Group**: `rg-dev-terprint-menudownloader`
- **Managed Identity**: `terprint-menu-downloader`
- **Output**: Azure Blob Storage (`storageacidnidatamover/jsonfiles`)

### Current Production Dispensaries
| Dispensary | Status | Downloader | Platform |
|------------|--------|------------|----------|
| Cookies | ✅ Active | `cookies_downloader.py` | REST API |
| MÜV | ✅ Active | `muv_downloader.py` | REST API |
| Flowery | ✅ Active | `flowery_downloader.py` | REST API |
| Trulieve | ✅ Active | `trulieve_downloader.py` | REST API |
| Sunburn | ✅ Active | `sunburn_downloader.py` | REST API |

### Pending (Ready for Integration from Menu Explorer)
| Dispensary | Config Location | Platform | Notes |
|------------|-----------------|----------|-------|
| Curaleaf | `config/terprint-config-curaleaf/` | HTML Scraping | 65 FL stores, ~85% terpene coverage |

---

## Receiving Handoffs from Menu Explorer

> 📥 **Menu Explorer discovers and validates dispensary APIs. When ready, they hand off to you.**

### What You Receive

When Menu Explorer completes discovery for a new dispensary, you receive:

| Artifact | Location | Description |
|----------|----------|-------------|
| **Config Package** | `config/terprint-config-{dispensary}/` | Ready-to-use Python module |
| **Scraper/Client Class** | `scraper.py` or `client.py` | Does the actual data fetching |
| **Config Class** | `config.py` | URLs, selectors, rate limits, field mappings |
| **Store List** | `config.py` (FL_STORES) | All Florida store IDs/slugs |
| **README** | `README.md` | Integration guide, output format, examples |
| **DevOps Work Item** | Azure DevOps | Links to discovery findings |

### Handoff Acceptance Checklist

Before integrating a new dispensary:

- [ ] Config package exists at `config/terprint-config-{dispensary}/`
- [ ] Scraper class is tested and working
- [ ] Store list includes all FL locations
- [ ] README documents output JSON format
- [ ] Rate limits are specified (don't get blocked!)
- [ ] Field mappings defined for COA Data Extractor

---

## Adding a New Dispensary (Step-by-Step)

> 🎯 **Goal: Minimal new code. Reuse the config package from Menu Explorer.**

### Step 1: Copy Config Package

```powershell
# Copy from Menu Explorer to Menu Downloader
Copy-Item -Recurse `
  "path/to/MenuExplorer/config/terprint-config-{dispensary}" `
  "src/terprint_menu_downloader/dispensaries/{dispensary}/"
```

### Step 2: Create Thin Wrapper Downloader

Create `src/terprint_menu_downloader/downloaders/{dispensary}_downloader.py`:

```python
"""
{Dispensary} Florida Downloader Module
Wrapper around the config package from Menu Explorer.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Import the scraper from the config package
from ..dispensaries.{dispensary} import {Dispensary}Scraper, FL_STORES, {DISPENSARY}_CONFIG


class {Dispensary}Downloader:
    """Download menu data from {Dispensary} Florida dispensaries."""

    def __init__(self, output_dir: str = "downloads", azure_manager=None):
        self.output_dir = output_dir
        self.azure_manager = azure_manager
        self.config = {DISPENSARY}_CONFIG
        self.stores = FL_STORES

    def download_location(self, store_slug: str) -> Optional[Dict]:
        """Download menu data for a specific store."""
        try:
            with {Dispensary}Scraper() as scraper:
                # Use scraper method from config package
                products = scraper.scrape_store_menu_with_terpenes(
                    store_slug,
                    sample_terpenes=None  # Get all terpenes
                )

            store_info = next((s for s in self.stores if s['slug'] == store_slug), {})

            return {
                "dispensary": "{dispensary}",
                "store_slug": store_slug,
                "store_name": store_info.get('name', store_slug),
                "state": "FL",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "product_count": len(products),
                "products": products,
                "metadata": {
                    "platform": self.config.platform,
                    "scrape_type": self.config.platform_type,
                    "terpene_source": self.config.terpene_source,
                }
            }
        except Exception as e:
            print(f"Error downloading {store_slug}: {e}")
            return None

    def download_all(self) -> Dict[str, List]:
        """Download from all FL stores."""
        print(f"\n{'='*60}")
        print(f"{self.config.dispensary_name} - Downloading {len(self.stores)} stores")
        print(f"{'='*60}\n")

        results = []
        for store in self.stores:
            # Skip delivery-only stores
            if 'delivery' in store['slug']:
                continue

            print(f"Downloading {store['slug']}...", end=" ")
            result = self.download_location(store['slug'])

            if result:
                results.append(result)
                print(f"✓ {result['product_count']} products")
            else:
                print("✗ Failed")

        return {
            "dispensary": "{dispensary}",
            "download_timestamp": datetime.now(timezone.utc).isoformat(),
            "store_count": len(results),
            "results": results
        }
```

### Step 3: Register in __init__.py

Edit `src/terprint_menu_downloader/downloaders/__init__.py`:

```python
from .{dispensary}_downloader import {Dispensary}Downloader

__all__ = [
    # ... existing ...
    '{Dispensary}Downloader',
]
```

### Step 4: Add to Orchestrator

Edit `src/terprint_menu_downloader/orchestrator.py`:

```python
# In imports section
from .downloaders import {Dispensary}Downloader

# In _initialize_dispensary_downloaders method
downloaders['{dispensary}'] = {
    'downloader': {Dispensary}Downloader(
        output_dir=self.output_dir,
        azure_manager=self.azure_manager
    )
}

# In _get_dispensary_display_name method
dispensary_names['{dispensary}'] = '{Display Name}'

# In _extract_batches_from_data method (add elif block)
elif dispensary == '{dispensary}':
    products = data.get('products', []) if isinstance(data, dict) else []
    for product in products:
        # Extract batch info based on config field_mappings
        pass
```

### Step 5: Test Locally

```python
# Quick test
from terprint_menu_downloader.downloaders import {Dispensary}Downloader

downloader = {Dispensary}Downloader()
result = downloader.download_location("store-slug-here")
print(f"Downloaded {result['product_count']} products")
```

---

## Curaleaf Integration (Ready Now)

> 📦 **Config package ready at:** `Terpint.Python.MenuExplorer/config/terprint-config-curaleaf/`

### What's Provided

| File | Purpose |
|------|---------|
| `config.py` | `CuraleafConfig` class with URLs, selectors, 65 FL stores |
| `scraper.py` | `CuraleafScraper` class - HTML scraping with httpx/BeautifulSoup |
| `README.md` | Full integration guide |
| `__init__.py` | Package exports |

### Key Details

- **Platform**: SweedPOS (HTML scraping, NOT REST API)
- **Rate Limit**: 500ms between detail page requests
- **Terpene Data**: Requires scraping product detail pages (~85% coverage)
- **Store Count**: 65 FL locations
- **Output Format**: See README.md for JSON structure

### Integration Commands

```powershell
# 1. Copy config package
Copy-Item -Recurse `
  "C:\...\Terpint.Python.MenuExplorer\config\terprint-config-curaleaf" `
  "C:\...\Terprint.Python.MenuDownloader\src\terprint_menu_downloader\dispensaries\curaleaf"

# 2. Create curaleaf_downloader.py (use template above)

# 3. Update __init__.py and orchestrator.py

# 4. Test
python -c "from terprint_menu_downloader.downloaders import CuraleafDownloader; d = CuraleafDownloader(); print(d.download_location('curaleaf-dispensary-tampa'))"
```

---

## Blob Storage Output Format

All downloaders must output JSON to this path pattern:

```
dispensaries/{dispensary}/{year}/{month}/{day}/{timestamp}.json
```

Example: `dispensaries/curaleaf/2025/12/16/20251216T120000Z.json`

---

## Handoff to COA Data Extractor

After a new dispensary is running in production:

1. Create DevOps Work Item in `Terprint\COA Data Extractor` area
2. Attach field mappings (from config package)
3. Attach sample JSON from Blob Storage
4. Notify COA Data Extractor team

---

## Core Development Principles

### Agile & Iterative Approach
- Break work into small, incremental changes aligned with 5-stage pipeline
- Deliver working software frequently (sprint-based delivery)
- Respond to dispensary API changes quickly (APIs can change without notice)
- Prioritize working code over comprehensive documentation (but maintain essential docs)
- Collaborate continuously with stakeholders
- Reflect and adjust processes regularly in retrospectives

### Code Quality Standards
- Write clean, readable, maintainable Python 3.12 code
- Follow SOLID principles and design patterns
- Implement comprehensive error handling (dispensary APIs are unreliable)
- Write self-documenting code with clear naming (domain terms: strain, batch, terpene, COA)
- Keep functions small and focused (single responsibility)
- Optimize for readability first, performance second (unless processing large JSON files)

## Technology Stack

### Required Technologies
| Component | Technology | Notes |
|-----------|------------|-------|
| **Cloud Platform** | Microsoft Azure | All resources in Azure |
| **Primary Language** | Python 3.12 | Azure Functions, data processing |
| **Secondary Language** | .NET (C#) | Marketplace metering service, admin site, webhook processor |
| **Compute** | Azure Functions | Serverless, timer-triggered & HTTP-triggered |
| **Storage** | Azure Blob Storage | Data lake for raw JSON files |
| **Database (Analytics)** | Azure Event House (Kusto/KQL) | Processed data: batch, strain, terpene, cannabinoid tables |
| **Database (Marketplace)** | Azure SQL | Subscriptions, metering, webhooks |
| **Queues** | Azure Storage Queues | Reliable event processing for marketplace |
| **Identity** | Azure Managed Identities | `mi-terprint-devops`, `terprint-menu-downloader`, `func-terprint-batchprocessor` |
| **Configuration** | terprint-config package | Centralized config via PyPI feed |
| **DevOps** | Azure DevOps | Acidni organization, Terprint project |
| **Monitoring** | Application Insights + Log Analytics | Observability for all components |
| **BI Tools** | Power BI + Custom Visuals | TypeScript + D3, packaged with pbiviz |

### Key Azure Resources
- **Function Apps**: `func-terprint-menudownloader`, `func-terprint-batchprocessor`
- **Storage Account**: `storageacidnidatamover` (jsonfiles container)
- **Resource Groups**: `rg-dev-terprint-menudownloader`, `rg-dev-terprint-batchprocessor`, `rg-dev-terprint-visuals`
- **Marketplace Stack**: App Service (landing/admin), Azure SQL, Key Vault, Function App (webhook), Storage Account

## Architecture Guidelines

### 5-Stage Pipeline Architecture

When working on any component, understand its position in the pipeline:

**Stage 1: Discovery (Development)**
- **Application**: Menu Discoverer
- **Purpose**: Find and validate NEW dispensary APIs before production
- **Activities**: API interception, request/response analysis, data structure mapping
- **Output**: Discovery findings → Azure DevOps → Validated configs → Menu Downloader

**Stage 2: Data Ingestion**
- **Application**: Menu Downloader (`func-terprint-menudownloader`)
- **Trigger**: Timer (daily 6 AM)
- **Process**: Fetch menus → Store raw JSON → Blob Storage (`dispensaries/{dispensary}/{year}/{month}/{day}/{timestamp}.json`)
- **Output**: Triggers Batch Processor
- **Production Dispensaries**: Cookies, MÜV, Flowery, Trulieve
- **Discovery Targets**: Sunnyside, Curaleaf, Liberty Health Sciences, Fluent, VidaCann, RISE

**Stage 3: Data Processing**
- **Application**: COA Data Extractor (Batch Processor) (`func-terprint-batchprocessor`)
- **Trigger**: HTTP (called by Menu Downloader)
- **Process**: Read JSON → Apply dispensary-specific mappings → Extract & normalize → Ingest to Event House
- **Records**: Batch, Strain, Terpene, Cannabinoid
- **Output**: Triggers website cache refresh

**Stage 4: Data Presentation**
- **Application**: Terprint Website
- **Process**: Query Event House → Serve search/filter UI → Display product details
- **Users**: Medical marijuana patients, dispensary staff

**Stage 5: Analytics**
- **Application**: Power BI Reports + Custom Visuals
- **Process**: Connect to Event House → Trend analysis → Scheduled reports
- **Custom Visuals**: TypeScript + D3 (terprint-powerbi-visuals/TerpeneRadar)

### Marketplace Integration Architecture
- **Azure SQL**: Plans, Subscriptions, UsageEvents, WebhookEvents (see `marketplace/database/schema.sql`)
- **Metering Service**: .NET background service → Aggregates usage → Submits to Microsoft Marketplace
- **Webhook Processor**: Azure Function (dotnet-isolated) → Receives Partner Center events → Updates subscriptions
- **Key Vault**: Partner Center credentials, SQL connection strings
- **Storage Queues**: Reliable webhook/usage event processing

### Architecture Decision Considerations
- **Service boundaries**: Each stage is a separate application with clear responsibilities
- **Communication**: Timer triggers (Stage 2) → HTTP triggers (Stage 3) → Cache refresh (Stage 4)
- **Data consistency**: Eventual consistency acceptable (daily batch processing)
- **Scalability**: Serverless functions auto-scale, Blob Storage handles large JSON files
- **Observability**: Application Insights for all stages, Log Analytics for queries

### Domain-Specific Design Patterns
- **Adapter Pattern**: Dispensary-specific field mappings (each dispensary API differs)
- **ETL Pattern**: Extract (download) → Transform (process) → Load (Event House)
- **Data Lake Pattern**: Store raw JSON in Blob Storage, process on-demand
- **Configuration as Code**: terprint-config package centralizes all configs

## Testing Framework

### Testing Pyramid (Cannabis Data Pipeline Context)

**Unit Tests (70% of tests)**
- Test individual dispensary API parsers in isolation
- Mock HTTP responses from dispensary APIs
- Test field mapping logic (strain name extraction, terpene percentage parsing)
- Verify COA data extraction accuracy
- Test Event House query builders
- Fast execution (< 1ms per test)
- Cover edge cases: missing fields, malformed JSON, null values
- Aim for 80%+ code coverage

**Integration Tests (20% of tests)**
- Test Menu Downloader → Blob Storage → Batch Processor flow
- Use Azure Storage Emulator or Azurite for local testing
- Test Event House ingestion with test database
- Verify dispensary config loading from terprint-config
- Test marketplace webhook processing end-to-end
- Test Power BI visual interactions with sample data

**End-to-End Tests (10% of tests)**
- Test complete pipeline: Download → Process → Query → Display
- Run against staging environment with test dispensary APIs
- Verify data appears correctly on website
- Test Power BI report refresh with real data
- Focus on critical paths: strain search, terpene filtering

### Domain-Specific Testing
- **API Contract Tests**: Verify dispensary API responses match expected schema (APIs change!)
- **Data Quality Tests**: Validate extracted terpene percentages sum correctly, batch numbers are valid
- **Idempotency Tests**: Ensure reprocessing same menu doesn't create duplicates
- **Resilience Tests**: Test behavior when dispensary APIs are down or return errors
- **Marketplace Tests**: Verify metering events, webhook processing, subscription lifecycle

### Test Data Management
- Maintain sample JSON files from each dispensary in `tests/fixtures/`
- Anonymize real dispensary data for test cases
- Version control test fixtures alongside code
- Update fixtures when dispensary APIs change

## Security Best Practices

### Application Security (Cannabis Data Context)
- **Input Validation**: Sanitize all dispensary API responses (untrusted external data)
- **Output Encoding**: Prevent XSS when displaying strain names, product descriptions
- **Authentication**: Azure Managed Identities for all inter-service communication
- **Secrets Management**: Use Azure Key Vault (never commit API keys, database connection strings)
- **Rate Limiting**: Respect dispensary API rate limits, implement exponential backoff
- **Data Privacy**: Handle patient data responsibly (if present in analytics)
- **Partner Center Security**: Service Principal credentials in Key Vault, managed identities for API calls

### Infrastructure Security
- **Managed Identities**: Use assigned identities for all Azure resources
  - `mi-terprint-devops` - Project Administrator
  - `terprint-menu-downloader` - Project Contributor
  - `func-terprint-batchprocessor` - Project Contributor
- **RBAC**: Principle of least privilege for all Azure resources
- **Network Segmentation**: Function apps communicate via private endpoints (when possible)
- **Blob Storage**: Secure access via managed identities, no public access
- **Event House**: Restrict access via Azure AD authentication
- **SQL Database**: Firewall rules, connection encryption, managed identity auth
- **Audit Logging**: Enable Azure Monitor for all resource access

### Compliance Considerations
- **Cannabis Industry**: Be aware of state/federal regulations around cannabis data
- **HIPAA**: If handling patient information, ensure HIPAA compliance
- **Data Retention**: Implement retention policies for raw JSON files in Blob Storage

## CI/CD Pipeline Requirements

### Azure DevOps Integration
- **Organization**: Acidni
- **Project**: Terprint
- **Area Paths**:
  - `Terprint` - Root (terprint-config)
  - `Terprint\Menu Downloader` - Menu Downloader issues
  - `Terprint\COA Data Extractor` - Batch Processor issues
- **Artifacts Feed**: terprint (PyPI) - hosts terprint-config package

### Continuous Integration
- **Build Triggers**: Every commit to main branch
- **Build Steps**:
  1. Restore Python dependencies (requirements.txt)
  2. Run unit tests (pytest)
  3. Run integration tests
  4. Code quality checks (pylint, black, mypy)
  5. Security scanning (Bandit for Python, dependency vulnerabilities)
  6. Build Azure Function zip packages
  7. Publish terprint-config to Azure Artifacts feed
- **Fast Feedback**: < 10 minutes for CI pipeline
- **Build Artifacts**: Function app zip files, terprint-config wheel

### Continuous Deployment
- **Environments**: Development → Staging → Production
- **Deployment Steps**:
  1. Deploy to dev environment (automatic)
  2. Run smoke tests (verify functions respond)
  3. Deploy to staging (automatic)
  4. Run E2E tests (verify full pipeline)
  5. Deploy to production (manual approval gate)
- **Rollback Strategy**: Redeploy previous version, restore Event House data from backup
- **Database Migrations**: Run Kusto scripts before function deployment, SQL migrations for marketplace
- **Configuration**: Update terprint-config package version in requirements.txt

### Marketplace Deployment
- **Bicep Templates**: `marketplace/infra/main.bicep`
- **Parameter Files**: `parameters.dev.json`, `parameters.prod.json`
- **Validation**: Non-interactive validation before deployment
- **Power BI Visuals**: Package with `pbiviz package`, submit to Partner Center/AppSource

## Code Review Guidelines

### Terprint-Specific Review Checklist

**When Submitting Code:**
- Keep PRs small (< 400 lines when possible)
- Include dispensary name in PR title if adding new dispensary support
- Test with real dispensary API responses (include sample JSON)
- Update terprint-config version and changelog
- Verify changes don't break existing dispensary mappings
- Include Event House query examples if schema changes
- Update Power BI visual version if modifying visuals
- Test marketplace metering/webhook locally before submission

**When Reviewing Code:**
- **Data Accuracy**: Verify field mappings are correct (strain name, terpene percentages)
- **Error Handling**: Check dispensary API failure scenarios
- **Performance**: Large JSON files can cause memory issues (check file size handling)
- **Idempotency**: Ensure reprocessing doesn't create duplicate records
- **Schema Compatibility**: Verify Event House schema changes are backward compatible
- **Configuration**: Check terprint-config changes don't break existing deployments
- **Security**: Verify managed identities used, no hardcoded secrets
- **Marketplace**: Verify metering logic, webhook event handling, SQL schema changes

### Domain-Specific Code Patterns to Watch For
- **Hardcoded Dispensary Mappings**: Should be in terprint-config, not inline
- **Brittle JSON Parsing**: Use safe dictionary access (`.get()` with defaults)
- **Missing Null Checks**: Dispensary APIs often return null/missing fields
- **Timezone Issues**: Timestamps should be UTC, display in EST for Florida users
- **Percentage Validation**: Terpene/cannabinoid percentages should sum correctly

## KPI Tracking & Metrics

### DORA Metrics (Terprint Context)
- **Deployment Frequency**: Target 2-3 deployments per week
- **Lead Time for Changes**: Commit to production < 4 hours
- **Change Failure Rate**: < 5% (critical: data accuracy errors)
- **Time to Restore Service**: < 2 hours (daily pipeline must complete)

### Data Pipeline Metrics
- **Data Freshness**: Time since last successful menu download (target: < 24 hours)
- **Dispensary Coverage**: % of Florida dispensaries with active data (currently 4, target: 10)
- **Data Quality**: % of menus with complete terpene profiles (target: > 90%)
- **Processing Time**: Time to process all menus (target: < 30 minutes)
- **Error Rate**: % of menu downloads that fail (target: < 10%)
- **Event House Ingestion Rate**: Records ingested per day (track growth)

### Code Quality Metrics
- **Code Coverage**: 80%+ for Python code
- **Cyclomatic Complexity**: < 10 per function
- **Code Duplication**: < 3%
- **Critical Vulnerabilities**: Zero
- **Technical Debt Ratio**: < 5%

### Business Metrics
- **Website Traffic**: Unique visitors per day
- **Search Queries**: Strain/terpene searches per day
- **Power BI Report Usage**: Report views per week
- **Dispensary API Uptime**: % of successful API calls per dispensary
- **Marketplace Subscriptions**: Active subscriptions, usage events submitted, webhook success rate

## Problem-Solving Workflow

### Dispensary API Troubleshooting
When a dispensary API fails or changes:

1. **Investigate**: Check Application Insights logs for error messages
2. **Reproduce**: Use Menu Discoverer to test API endpoint locally
3. **Analyze**: Compare old vs new API response structure
4. **Design**: Update field mappings in terprint-config
5. **Implement**: Modify Batch Processor to handle new structure
6. **Test**: Verify with real API responses (save sample JSON)
7. **Deploy**: Publish terprint-config, update Menu Downloader/Batch Processor
8. **Monitor**: Watch Application Insights for 24 hours

### Adding New Dispensary (Discovery → Production)

**📋 Full handoff documentation: `docs/DISPENSARY_HANDOFF.md`**

#### What Menu Explorer Must Provide
Before Menu Downloader can add a new dispensary, you must receive:

| Artifact | Description | Required? |
|----------|-------------|-----------|
| Discovery Findings | API endpoint, method, headers, auth, rate limits | ✅ Required |
| Store List | FL stores with IDs, names, addresses | ✅ Required |
| Sample JSON | Full API response saved as `{dispensary}_sample.json` | ✅ Required |
| Field Mappings | JSONPath for batch, strain, terpenes, cannabinoids | ✅ Required |
| Validation Results | 7-day API stability test results | ✅ Required |
| DevOps Work Item | Linked handoff task with all artifacts attached | ✅ Required |

#### Menu Downloader Implementation Steps
1. **Receive Handoff Work Item**: Check Azure DevOps for new dispensary tasks
2. **Review Artifacts**: Validate all required files are attached
3. **Add Store List**: Update `terprint-config/shared/dispensary-stores.json`:
   ```json
   {
     "displayName": "NewDispensary",
     "state": "FL",
     "storeIdType": "slug|numeric_range|string",
     "storeCount": 12,
     "stores": [{"id": "store-1", "name": "Store 1", "city": "Miami", "address": "...", "zip": "33101"}]
   }
   ```
4. **Create Downloader Class**: `terprint-python/Terprint.Python.MenuDownloader/downloaders/{dispensary}_downloader.py`
5. **Add to Config**: Update `config.json`:
   ```json
   {
     "dispensary": "newdispensary",
     "enabled": true,
     "apiType": "rest|graphql",
     "schedule": "0 0 6 * * *"
   }
   ```
6. **Test Download**: Run locally and verify JSON stored to Blob
7. **Verify Blob Path**: `dispensaries/{dispensary}/{year}/{month}/{day}/{timestamp}.json`
8. **Close Work Item**: Link PR and update status

#### Blob Storage Path Structure
```
dispensaries/
├── cookies/
│   └── 2025/12/16/06-00-00.json
├── muv/
│   └── 2025/12/16/06-00-00.json
├── flowery/
│   └── 2025/12/16/06-00-00.json
└── newdispensary/   <-- Create this structure
    └── 2025/12/16/06-00-00.json
```

#### Handoff Checklist (Menu Downloader Team)
- [ ] DevOps work item received and reviewed
- [ ] Store list JSON added to dispensary-stores.json
- [ ] Downloader class created
- [ ] Config entry added with enabled: true
- [ ] Timer schedule configured
- [ ] Test download successful locally
- [ ] JSON appears in Blob Storage
- [ ] PR submitted with tests
- [ ] Work item closed and linked to COA Extractor item

### Event House Schema Changes
1. **Backward Compatibility**: Ensure existing queries still work
2. **Migration Plan**: Write Kusto script to backfill existing data
3. **Power BI Updates**: Update reports to use new schema
4. **Website Updates**: Update website queries
5. **Testing**: Verify all downstream consumers work
6. **Rollout**: Deploy schema changes before application changes

### Marketplace Issues (Metering/Webhooks)
1. **Check Logs**: Application Insights for metering service and webhook function
2. **Verify Events**: Check Azure SQL tables (UsageEvents, WebhookEvents)
3. **Partner Center**: Verify events received by Microsoft Marketplace
4. **Queue Messages**: Check Storage Queue for failed messages
5. **Credentials**: Verify Key Vault secrets, managed identity permissions
6. **Retry Logic**: Ensure idempotent processing for replayed events

## Communication Standards

### Documentation Requirements
- **README**: Each application (menu-downloader, coa-data-extractor, menu-discoverer, marketplace)
  - Setup instructions
  - Architecture overview
  - API documentation
  - Local development guide
- **terprint-config**: Comprehensive dispensary mapping documentation
- **Event House Schema**: Table definitions, sample queries
- **Power BI Visuals**: Development, packaging, submission guide
- **Marketplace**: Infrastructure deployment, parameters, SQL schema
- **ADR (Architecture Decision Records)**: Document major decisions (e.g., why Event House vs SQL for analytics)

### Azure DevOps Work Items
- **Bug**: Critical data accuracy issues, pipeline failures
- **Task**: New dispensary support, feature enhancements, medium/low priority
- **Area Path**: Assign to correct area (Terprint, Menu Downloader, COA Data Extractor)
- **Tags**: Use dispensary names, "data-quality", "performance", "security", "marketplace"
- **Discovery Findings**: Report in Menu Downloader area

### Commit Message Format
Use conventional commits:
- `feat(cookies): add support for new terpene fields`
- `fix(batch-processor): handle missing strain names`
- `chore(config): bump terprint-config to v1.2.3`
- `docs(readme): update Event House query examples`
- `test(muv): add fixtures for MÜV menu structure`
- `refactor(marketplace): extract metering logic into separate service`

### Sprint Planning
- **Sprint Duration**: 2 weeks
- **Velocity Tracking**: Story points per sprint
- **Priorities**:
  1. Critical bugs (data accuracy, pipeline failures)
  2. New dispensary support (expand coverage)
  3. Data quality improvements
  4. Performance optimizations
  5. Technical debt reduction
  6. Marketplace enhancements

### Stand-up Format
- **What I did**: Completed Flowery API update, fixed terpene parsing bug
- **What I'm doing**: Adding Sunnyside dispensary support
- **Blockers**: Waiting for Sunnyside API documentation
- **Dispensary Status**: All 4 production dispensaries healthy

## Iterative Improvement

This framework is a living document specific to Terprint. Regularly:

### Technical Improvements
- Review dispensary API reliability, consider backup data sources
- Optimize Batch Processor for larger JSON files
- Improve Event House query performance
- Enhance Power BI visual performance (TerpeneRadar render time)
- Reduce marketplace metering latency

### Process Improvements
- Refine discovery process for new dispensaries
- Streamline deployment pipeline (reduce manual steps)
- Improve monitoring dashboards (Application Insights queries)
- Enhance code review checklist based on common issues
- Document tribal knowledge about dispensary API quirks

### Business Improvements
- Expand dispensary coverage (target: 10 dispensaries)
- Improve data quality (complete terpene profiles)
- Reduce pipeline processing time
- Enhance website search relevance
- Add new Power BI visuals and reports
- Grow marketplace subscriptions and usage

## Current Sprint Focus

### Sprint Goals
[Update this section each sprint with specific goals, priorities, and context]

**Example:**
- **Goal 1**: Add Sunnyside and Curaleaf dispensary support
- **Goal 2**: Improve Batch Processor performance (reduce processing time by 30%)
- **Goal 3**: Launch marketplace metering service to production
- **Priority Bugs**: Fix MÜV terpene parsing for new menu format
- **Technical Debt**: Refactor Menu Downloader error handling

### Dispensary Status
- ✅ **Cookies**: Stable
- ✅ **MÜV**: Stable
- ✅ **Flowery**: Stable
- ✅ **Trulieve**: Stable
- 🔴 **Sunnyside**: Discovery in progress
- 🔴 **Curaleaf**: Discovery in progress

### Key Metrics This Sprint
- Pipeline Success Rate: 95%
- Data Freshness: < 24 hours
- Event House Records: 50K+ (growing)
- Website Uptime: 99.9%
- Marketplace Subscriptions: [Update with current count]

---

**Remember**: 
- **Data Accuracy is Critical**: Cannabis patients rely on accurate terpene/cannabinoid data
- **Dispensary APIs Change Often**: Build resilient, flexible parsers
- **Azure Managed Identities**: Never hardcode credentials
- **Domain Knowledge Matters**: Understand cannabis terminology (strain types, terpene effects, COA interpretation)
- **Quality Over Speed**: Accurate data > fast but wrong data
- **Marketplace Reliability**: Customers depend on metering accuracy and webhook processing

**Key Commands**:
```bash
# Local development
cd menu-downloader && func start
cd coa-data-extractor && func start
cd terprint-powerbi-visuals/TerpeneRadar && npm run start:TerpeneRadar

# Packaging
cd terprint-config && python -m build
cd TerpeneRadar && pbiviz package

# Deployment
az deployment group create -g rg-dev-terprint-visuals -f marketplace/infra/main.bicep -p @parameters.dev.json

# Testing
pytest tests/ --cov=terprint --cov-report=html
```

**Useful Resources**:
- Azure DevOps: https://dev.azure.com/Acidni/Terprint
- terprint-config docs: Azure Artifacts feed
- Power BI Visual Tools: https://github.com/microsoft/PowerBI-visuals-tools
- Kusto Query Language: https://docs.microsoft.com/en-us/azure/data-explorer/kusto/query/
