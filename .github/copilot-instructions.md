# Terprint AI Software Engineer & Architect Guidelines

---

> **📚 INHERITANCE**: This file contains **Terprint-specific** instructions.
> It inherits from and extends the **[Acidni Master Instructions](../shared/acidni-copilot-instructions.md)**.
> See also: **[.github/instructions/](./instructions/)** for technology-specific guidance.

---

## 🔗 Inherited From Acidni Master

The following standards are inherited from `shared/acidni-copilot-instructions.md`:
- Repository boundaries and cross-repo coordination
- Azure authentication (Entra ID, managed identities)
- Code quality standards (linting, testing, reviews)
- Security best practices (secrets, input validation)
- CI/CD and conventional commits
- General Python, TypeScript, and C# standards

**This file adds Terprint-specific context:**
- Cannabis dispensary domain knowledge
- 5-stage data pipeline architecture
- Terprint service configurations and ports
- Dispensary API mappings and integrations
- Azure Marketplace metering

---

## 🚨 CRITICAL DIRECTIVES — READ FIRST 🚨

> **THESE RULES ARE MANDATORY. VIOLATIONS WILL BREAK THE SYSTEM.**

### DIRECTIVE 1: NEVER MODIFY CODE OUTSIDE YOUR APP'S HOME REPO

- **EACH APP LIVES IN ITS OWN REPOSITORY** — Do NOT edit files in sibling repos
- **ALL CODE CHANGES ARE COORDINATED BY `terprint-config`** — Cross-cutting changes go through the config project
- **CREATE DEVOPS WORK ITEMS** to track config changes needed across repos
- If you need changes in another repo, document the requirement and create a work item
- Example: If `terprint-ai-chat` needs a config update, create WI in DevOps, don't edit `terprint-config` directly

### DIRECTIVE 2: USE `pymssql` NOT `pyodbc` FOR SQL

- Azure Functions Consumption Plan runs on **Linux without ODBC drivers**
- `pyodbc` WILL FAIL in production
- Always use `pymssql` with `%s` placeholders (not `?`)

### DIRECTIVE 3: USE ENTRA ID FOR SERVICE-TO-SERVICE AUTH

- **NEVER use function keys** for app-to-app API calls
- **NEVER hard-code API keys** in source code
- **ALWAYS use managed identities** and Bearer tokens
- **ALWAYS validate token audience** to prevent reuse attacks

### DIRECTIVE 4: MAINTAIN OPENAPI SPECS FOR ALL HTTP APIS

- Every Azure Function with HTTP triggers **MUST have `openapi.json`** in repo root
- Follow OpenAPI 3.0.x specification
- Include all endpoints, auth requirements, request/response schemas
- These are collected by `create-consolidated-readme.ps1` for APIM configuration

### DIRECTIVE 5: MAINTAIN DOCUMENTATION

- Every repo **MUST have** `README.md`, `docs/ARCHITECTURE.md`, `docs/INTEGRATION.md`
- Keep docs in sync with code changes (update in same PR)
- Run `copy-instructions.ps1` to get latest shared guidelines

### DIRECTIVE 6: TRIGGER INTEGRATION TESTS AFTER DEPLOYMENT

- All deployments **SHOULD trigger** `Terprint.Tests` pipeline
- See [CI_CD_INTEGRATION.md](../Terprint.Tests/docs/CI_CD_INTEGRATION.md) for setup
- Test dashboard: https://brave-stone-0d8700d0f.3.azurestaticapps.net

### DIRECTIVE 7: CI/CD PIPELINE CONFIGURATION

- **All deployments are managed by `terprint-pipeline`** — Do NOT create custom pipelines in component repos
- **Pipeline Documentation**: [terprint-pipeline/docs](https://github.com/Acidni-LLC/terprint-pipeline/tree/main/docs)
- **Build Order**: Dependencies must build before dependents (see pipeline docs)
- **Environment Promotion**: dev → staging → prod with manual approval gates
- **Secrets**: All secrets must be in Azure Key Vault, referenced by pipeline variables
- **Deployment Triggers**: Automatic for dev, manual approval for prod
- **Artifact Publishing**: All builds publish to Azure Artifacts feed

---

## Project Context

You are an expert software engineer and architect working on **Terprint** - a data pipeline system that aggregates, processes, and presents cannabis dispensary menu data for Florida medical marijuana dispensaries. The system collects product information including strain names, batch numbers, terpene profiles, and cannabinoid percentages.

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

### Critical Development Directives

> ⚠️ **MANDATORY RULES** - Follow these directives without exception unless explicitly approved.

#### SQL Database Drivers (Python)
| DO NOT USE | USE INSTEAD | Reason |
|------------|-------------|--------|
| `pyodbc` | `pymssql` | Azure Functions Consumption Plan lacks ODBC drivers (Linux) |

**Placeholder Syntax Difference:**
```python
# ❌ WRONG - pyodbc style (will NOT work with pymssql)
cursor.execute("SELECT * FROM Users WHERE Id = ?", (user_id,))

# ✅ CORRECT - pymssql style
cursor.execute("SELECT * FROM Users WHERE Id = %s", (user_id,))
```

**Exception**: Only use `pyodbc` if running on Windows App Service Plan with ODBC drivers installed, and document the exception in the code.

#### Azure Functions Authentication
| DO NOT USE | USE INSTEAD | Reason |
|------------|-------------|--------|
| `AuthorizationLevel.Anonymous` | `AuthorizationLevel.Function` | Security - all endpoints must require function keys |

**Python (function.json):**
```json
// ❌ WRONG - Anonymous access (NO authentication)
{
  "authLevel": "anonymous",
  "type": "httpTrigger"
}

// ✅ CORRECT - Function key required
{
  "authLevel": "function",
  "type": "httpTrigger"
}
```

**C# (.NET):**
```csharp
// ❌ WRONG - Anonymous access
[Function("MyFunction")]
public IActionResult Run([HttpTrigger(AuthorizationLevel.Anonymous)] HttpRequest req)

// ✅ CORRECT - Function key required
[Function("MyFunction")]
public IActionResult Run([HttpTrigger(AuthorizationLevel.Function)] HttpRequest req)
```

**Exception**: Only use `Anonymous` for public health check endpoints (e.g., `/api/health`) that return no sensitive data, and document the exception. Alternative: Use `Anonymous` with manual API key validation when supporting multiple auth header formats (X-API-Key, x-functions-key, code query param) - document the validation pattern.

#### Component Documentation Requirements

> 📚 **MANDATORY**: Every Terprint component MUST maintain its own documentation.

Each component repository must include:

| Document | Purpose | Required |
|----------|---------|----------|
| `README.md` | Overview, setup, quick start | ✅ Yes |
| `openapi.json` | OpenAPI 3.0 spec for all HTTP endpoints | ✅ Yes (for APIs) |
| `docs/ARCHITECTURE.md` | System design, data flow diagrams, dependencies | ✅ Yes |
| `docs/INTEGRATION.md` | How other apps integrate with this component | ✅ Yes |
| `docs/USAGE.md` | API reference, endpoints, examples | ✅ Yes |
| `docs/TESTING.md` | Test strategy, how to run tests, coverage | ✅ Yes |
| `docs/ADMIN_GUIDE.md` | Deployment, configuration, monitoring | For services |
| `docs/USER_GUIDE.md` | End-user documentation | For user-facing apps |

**OpenAPI Specification Requirements (for all Azure Functions with HTTP triggers):**
- Place `openapi.json` in the repository root
- Follow OpenAPI 3.0.x specification
- Include all HTTP-triggered endpoints with request/response schemas
- Document authentication requirements (Bearer token, scopes)
- Include example requests and responses
- Used by APIM for automatic API configuration
- Run `create-consolidated-readme.ps1` to collect all OpenAPI specs centrally

**Documentation Quality Standards:**
- Include Mermaid diagrams for architecture and data flows
- Document all environment variables and configuration
- Provide troubleshooting guides for common issues
- Keep docs in sync with code changes (update docs in same PR as code)

**Backup Process:**
- Component docs are periodically gathered into `terprint-config` for centralized backup
- If a component has better docs than central config, the component's docs become authoritative
- Run `copy-instructions.ps1` to distribute updated standards to all repos

#### App-to-App Authentication (Entra ID)

> 🔐 **MANDATORY**: All service-to-service API calls MUST use Entra ID app-to-app authentication.

| DO NOT DO | DO INSTEAD | Reason |
|-----------|------------|--------|
| Use function keys for app-to-app calls | Use Entra ID Bearer tokens | Proper identity-based security |
| Hard-code API keys in code | Use managed identities | Keys can leak, identities can't |
| Trust any incoming request | Validate Bearer tokens | Verify caller identity and permissions |
| Skip audience validation | Always validate token audience | Prevent token reuse attacks |

**Architecture Overview:**
Each Terprint service has its own Entra ID app registration:
- Apps expose API scopes (e.g., `Communications.Send`, `BatchProcessor.Execute`)
- Apps request permissions to call other apps' APIs
- Managed Identity (in Azure) acquires tokens automatically
- APIs validate incoming tokens for audience, issuer, and scopes

**App Registration Names:**
| App | Application ID URI | Primary Scopes |
|-----|-------------------|----------------|
| `func-terprint-communications` | `api://func-terprint-communications` | Communications.Send, Communications.Read |
| `func-terprint-batchprocessor` | `api://func-terprint-batchprocessor` | BatchProcessor.Execute, BatchProcessor.Read |
| `func-terprint-menudownloader` | `api://func-terprint-menudownloader` | MenuDownloader.Download, MenuDownloader.StockCheck |
| `func-terprint-ai-chat` | `api://func-terprint-ai-chat` | AIChat.Query, AIChat.History |
| `func-terprint-ai-recommender` | `api://func-terprint-ai-recommender` | AIRecommender.GetRecommendations |
| `func-terprint-ai-deals` | `api://func-terprint-ai-deals` | AIDeals.Analyze, AIDeals.Read |
| `func-terprint-ai-health` | `api://func-terprint-ai-health` | AIHealth.Monitor, AIHealth.Alerts |
| `terprint-marketplace-webhook` | `api://terprint-marketplace-webhook` | Marketplace.Webhook |

**Permission Matrix (who can call whom):**
```
Menu Downloader → Batch Processor, Communications
Batch Processor → Communications, AI Chat, AI Recommender
AI Chat → AI Recommender, AI Deals, Communications, Menu Downloader
AI Recommender → AI Deals, Communications
AI Deals → Communications
AI Health → ALL services (monitoring)
Marketplace Webhook → Communications
Web App → Communications, Menu Downloader, AI Chat, AI Recommender, AI Deals
```

**Calling Another Service (Python):**
```python
from terprint_config.auth import get_auth_header, get_access_token

# Option 1: Get auth header directly
headers = get_auth_header("func-terprint-communications")
response = requests.post(url, headers=headers, json=data)

# Option 2: Get token for more control
result = get_access_token("func-terprint-communications")
if result.success:
    headers = {"Authorization": f"Bearer {result.token}"}
    response = requests.post(url, headers=headers, json=data)
```

**Validating Incoming Tokens (Python):**
```python
from terprint_config.auth import validate_token, require_auth
import os

# Option 1: Manual validation
auth_header = request.headers.get("Authorization")
result = validate_token(
    auth_header,
    expected_audience=os.environ["AZURE_CLIENT_ID"],
    required_scopes=["Communications.Send"]
)
if not result.valid:
    return {"error": result.error}, 401

# Option 2: Decorator (Azure Functions)
@require_auth(required_scopes=["Communications.Send"])
def send_email(req: func.HttpRequest) -> func.HttpResponse:
    # Token already validated, proceed with logic
    pass
```

**Required Environment Variables:**
```json
{
  "AZURE_TENANT_ID": "3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd",
  "AZURE_CLIENT_ID": "<your-app-client-id>"
}
```

**Required Packages:**
```
azure-identity>=1.15.0    # For token acquisition
PyJWT[crypto]>=2.8.0      # For token validation
```

**Migration Path (function keys → Entra ID):**
1. Add Entra ID auth alongside existing function keys
2. Update callers to send both Bearer token AND function key
3. Verify all callers are sending Bearer tokens
4. Remove function key validation from endpoints
5. Remove function keys from callers

**Exception**: Health check endpoints (`/api/health`) may remain anonymous for load balancer probes.

#### Sample Code Usage Requirements

> 🔍 **MANDATORY**: Apps MUST search for existing sample code before writing new implementations.

| DO NOT DO | DO INSTEAD | Reason |
|-----------|------------|--------|
| Write JSON parsing from scratch | Find sample code in `shared/samples/` | Reduces coding errors |
| Create new API integration patterns | Reference existing dispensary integrations | Proven patterns work |
| Implement data mappings manually | Use `shared/dispensary-mappings.json` | Centralized, tested configs |
| Build communications features | Use `func-terprint-communications` helpers | Single source of truth |

**Before writing any new code:**
1. Check `shared/samples/` for JSON samples of the data you're working with
2. Check `shared/` for existing mapping configurations
3. Check `terprint_config/` for helper functions and utilities
4. Check existing dispensary implementations for proven patterns
5. If sample code exists, COPY and ADAPT it - don't reinvent

**Why this matters:**
- Too many simple mistakes happen when writing code from scratch
- Sample code has been tested and validated
- Using existing patterns ensures consistency across all apps
- Reduces debugging time and integration issues

**Exception**: Only write from scratch when no suitable sample exists, and then CREATE a sample for others to use.

#### Local Function App Testing Requirements

> 🧪 **MANDATORY**: Always test Azure Function Apps locally before deploying to Azure.

| DO NOT DO | DO INSTEAD | Reason |
|-----------|------------|--------|
| Deploy untested functions directly to Azure | Run `func host start` locally first | Catch errors before deployment |
| Test only in Azure portal | Test all endpoints with local URLs | Faster iteration, no deployment wait |
| Skip local environment setup | Configure `local.settings.json` properly | Consistent local/cloud behavior |

**Local Testing Process:**
1. **Build the project first**: `dotnet build` (C#) or ensure `requirements.txt` installed (Python)
2. **Run the function host**: Use VS Code task `func: host start` or terminal `func host start`
3. **Test ALL endpoints**: Use REST client, Postman, or curl against `http://localhost:7071`
4. **Verify logs**: Check terminal output for errors and expected behavior
5. **Test error cases**: Try invalid inputs, missing parameters, auth failures

**Assigned Local Testing Ports:**
Each app has 5 dedicated ports to allow running multiple services simultaneously:

| App | Ports | Default | Window Title |
|-----|-------|---------|--------------|
| `func-terprint-communications` | 7071-7075 | 7071 | 🔔 Communications |
| `func-terprint-batchprocessor` | 7076-7080 | 7076 | 📦 Batch Processor |
| `func-terprint-menudownloader` | 7081-7085 | 7081 | 📥 Menu Downloader |
| `func-terprint-ai-chat` | 7086-7090 | 7086 | 💬 AI Chat |
| `func-terprint-ai-recommender` | 7091-7095 | 7091 | 🎯 AI Recommender |
| `func-terprint-ai-deals` | 7096-7100 | 7096 | 💰 AI Deals |
| `func-terprint-ai-health` | 7101-7105 | 7101 | 🏥 AI Health |
| `terprint-marketplace-webhook` | 7106-7110 | 7106 | 🏪 Marketplace Webhook |
| `func-terprint-infographics` | 7111-7115 | 7111 | 🎨 Infographics |
| `func-terprint-metering` | 7116-7120 | 7116 | 📊 Metering |
| `func-terprint-data-api` | 7121-7125 | 7121 | 📡 Data API |

#### Deployment Targets (Where to Deploy Each App)

> 🚀 **MANDATORY**: Deploy to the correct Azure resource. Each app has a specific deployment target.

| App | Type | Azure Resource | Resource Group | URL |
|-----|------|----------------|----------------|-----|
| `func-terprint-communications` | Azure Functions | `func-terprint-communications` | `rg-dev-terprint-shared` | `func-terprint-communications.azurewebsites.net` |
| `func-terprint-batchprocessor` | Azure Functions | `func-terprint-batchprocessor` | `rg-dev-terprint-batchprocessor` | `func-terprint-batchprocessor.azurewebsites.net` |
| `func-terprint-menudownloader` | Azure Functions | `func-terprint-menudownloader` | `rg-dev-terprint-menudownloader` | `func-terprint-menudownloader.azurewebsites.net` |
| `func-terprint-ai-chat` | Azure Functions | `func-terprint-ai-chat` | `rg-dev-terprint-shared` | `func-terprint-ai-chat.azurewebsites.net` |
| `func-terprint-ai-recommender` | Azure Functions | `func-terprint-ai-recommender` | `rg-dev-terprint-shared` | `func-terprint-ai-recommender.azurewebsites.net` |
| `func-terprint-ai-deals` | Azure Functions | `func-terprint-ai-deals` | `rg-dev-terprint-shared` | `func-terprint-ai-deals.azurewebsites.net` |
| `func-terprint-ai-health` | Azure Functions | `func-terprint-ai-health` | `rg-dev-terprint-shared` | `func-terprint-ai-health.azurewebsites.net` |
| `terprint-marketplace-webhook` | Azure Functions (.NET) | `func-terprint-marketplace` | `rg-terprint-marketplace` | `func-terprint-marketplace.azurewebsites.net` |
| `func-terprint-infographics` | Azure Functions | `func-terprint-infographics` | `rg-dev-terprint-shared` | `func-terprint-infographics.azurewebsites.net` |
| `func-terprint-metering` | Azure Functions | `func-terprint-metering` | `rg-dev-terprint-shared` | `func-terprint-metering.azurewebsites.net` |
| `func-terprint-data-api` | Azure Functions | `func-terprint-data-api` | `rg-dev-terprint-shared` | `func-terprint-data-api.azurewebsites.net` |
| `terprint-sales` | Static Web App | `swa-terprint-sales` | `rg-dev-terprint-shared` | `sales.terprint.com`, `terprint.com`, `www.terprint.com` |
| `Terprint.Web` | App Service | `terprint-web` | `rg-terprint-web` | `terprint.acidni.net` |
| `terprint-powerbi-visuals` | Power BI AppSource | Partner Center | N/A | AppSource |

**Deployment Commands:**

```bash
# Azure Functions (Python) - from function app directory
func azure functionapp publish <function-app-name>

# Azure Functions (.NET) - from project directory
dotnet publish -c Release
func azure functionapp publish <function-app-name>

# Static Web App - from site directory
swa deploy . --deployment-token "<token>" --env production

# App Service (.NET) - from project directory
dotnet publish -c Release -o ./publish
az webapp deploy --resource-group <rg> --name <app> --src-path ./publish.zip

# Power BI Visual - from visual directory
pbiviz package
# Then submit to Partner Center
```

**Getting Deployment Tokens (Static Web Apps):**
```bash
# Get SWA deployment token
az staticwebapp secrets list --name "swa-terprint-sales" --resource-group "rg-dev-terprint-shared" --query "properties.apiKey" -o tsv
```

**VS Code Extension Deployment:**
For Azure Functions, use the Azure Functions VS Code extension:
1. Right-click on the function app in Azure explorer
2. Select "Deploy to Function App..."
3. Choose the correct function app from the list

**IMPORTANT**: Always verify you're deploying to the correct resource before executing deployment commands!

**Use `terprint_config` helpers for local testing:**
```python
from terprint_config import get_default_port, get_window_title, get_local_start_command

# Get the default port for an app
port = get_default_port("func-terprint-communications")  # 7071

# Get window title with emoji
title = get_window_title("func-terprint-communications")  # "🔔 Communications (7071)"

# Get full PowerShell command to start with titled window
cmd = get_local_start_command("func-terprint-communications")
# '$Host.UI.RawUI.WindowTitle = "🔔 Communications (7071)"; func host start --port 7071'
```

**Starting multiple apps locally:**
```powershell
# Terminal 1 - Communications (port 7071)
$Host.UI.RawUI.WindowTitle = "🔔 Communications (7071)"; func host start --port 7071

# Terminal 2 - Batch Processor (port 7076)  
$Host.UI.RawUI.WindowTitle = "📦 Batch Processor (7076)"; func host start --port 7076

# Terminal 3 - Menu Downloader (port 7081)
$Host.UI.RawUI.WindowTitle = "📥 Menu Downloader (7081)"; func host start --port 7081
```

**VS Code Integration:**
```json
// Use existing VS Code tasks for local testing:
// "func: 4" task runs the function app locally after build
// Tasks > Run Task > "func: 4" (or F5 with launch.json configured)
```

**Environment Setup:**
```json
// local.settings.json must include all required settings:
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "dotnet-isolated",
    // Add all connection strings and app settings
  }
}
```

**Exception**: Quick configuration-only changes (not code) may skip local testing if they've been validated in a staging environment.

### Integration Testing

**HTTP Integration Tests** (`Terprint.IntegrationTests` project):
Tests run against deployed services - no local project references needed.

```bash
# Run communications tests
dotnet test --filter "Component=Communications"

# Run all integration tests
cd Terprint.IntegrationTests
dotnet test
```

**Service Documentation Scavenging** 📚

> **Before writing tests, scan other repo READMEs for API documentation!**

Each component repo contains API documentation in its README:

| Service | Repo README | Key Endpoints |
|---------|-------------|---------------|
| AI Chat | `terprint-ai-chat/README.md` | `/api/chat`, `/api/health` |
| AI Recommender | `terprint-ai-recommender/README.md` | `/api/recommend`, `/api/health` |
| AI Deals | `terprint-ai-deals/README.md` | `/api/deals`, `/api/health` |
| Menu Downloader | `func-terprint-menudownloader/README.md` | `/api/menu`, `/api/stock-check` |
| Batch Processor | `func-terprint-batchprocessor/README.md` | `/api/run-batch-processor` |
| Communications | `func-terprint-communications/README.md` | `/api/send-email`, `/api/send-sms` |
| Marketplace Webhook | `terprint-marketplace-webhook/README.md` | `/api/marketplace-webhook` |
| Health Dashboard | `terprint-ai-health/README.md` | `/api/health`, `/api/diagram` |

**Configuration**: See `Terprint.Tests/test-config.json` for all service endpoints.

---

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

---

## 📋 AZURE RESOURCES QUICK REFERENCE

> **DO NOT ASK** about these resources. This is the authoritative reference.

### Function Apps (Complete List)

| Function App | Resource Group | Purpose | State |
|--------------|----------------|---------|-------|
| `func-dev-terprint-ai-chat` | `rg-dev-terprint-ai-chat` | AI Chat service | Running |
| `terprint-menu-downloader` | `rg-dev-terprint-menudownloader` | Menu data ingestion | Running |
| `func-terprint-ai-recommender` | `rg-dev-terprint-ai-recommender` | Strain recommendations | Running |
| `func-terprint-batchprocessor` | `rg-dev-terprint-batchprocessor` | COA data extraction | Running |
| `func-terprint-ai-deals` | `rg-dev-terprint-ai-deals` | Deal analysis | Running |
| `func-terprint-infographics` | `rg-dev-terprint-infographics` | Image generation | Running |
| `func-terprint-coadataextractor` | `rg-dev-terprint-coadataextractor` | COA parsing | Running |
| `func-terprint-data-api` | `rg-dev-terprint-data-api` | Data access API | Running |
| `func-terprint-marketplace` | `rg-dev-terprint-marketplace` | Marketplace webhooks | Running |

### Static Web Apps

| App | Hostname | Purpose |
|-----|----------|---------|
| `swa-terprint-sales` | `green-forest-02ff0c80f.3.azurestaticapps.net` | Sales website (sales.terprint.com) |
| `swa-terprint-tests-dev` | `brave-stone-0d8700d0f.3.azurestaticapps.net` | Test dashboard |
| `swa-acidni-website` | `zealous-stone-0fafe420f.6.azurestaticapps.net` | Acidni corporate site |

### APIM (apim-terprint-dev) - API Gateway

**Base URL**: `https://apim-terprint-dev.azure-api.net`

| API ID | Display Name | Path | Backend |
|--------|--------------|------|---------|
| `terprint-communications` | Communications API | `/communications` | func-terprint-communications |
| `terprint-ai-chat-api` | Terprint AI Chat API | `/chat` | func-dev-terprint-ai-chat |
| `terprint-ai-recommender-api` | Terprint AI Recommender API | `/recommend` | func-terprint-ai-recommender |
| `terprint-data-api` | Terprint Data API | `/data` | func-terprint-data-api |
| `terprint-infographics` | Terprint Infographics API | `/infographics` | func-terprint-infographics |
| `terprint-stock-api` | Terprint Stock API | `/stock` | terprint-menu-downloader |
| `terprint-ai-lab` | Terprint AI Lab API | `/lab` | Experimental |

### Communications API Endpoints (terprint-communications)

| Method | Endpoint | Operation | Description |
|--------|----------|-----------|-------------|
| POST | `/communications/send-email` | send-email | Send email via Azure Communication Services |
| POST | `/communications/send-sms` | send-sms | Send SMS via Azure Communication Services |
| POST | `/communications/send-batch-notification` | send-batch-notification | Batch notifications |
| POST | `/communications/ai-chat/send-email` | ai-chat-send-email | AI Chat email integration |
| POST | `/communications/ai-chat/send-sms` | ai-chat-send-sms | AI Chat SMS integration |
| GET | `/communications/ai-chat/conversation` | ai-chat-conversation | Get SMS conversation history |
| POST | `/communications/chat-messages` | chat-messages | Chat webhook |
| POST | `/communications/email-events` | email-events | Email event webhook |
| POST | `/communications/sms-inbound` | sms-inbound | Inbound SMS webhook |
| GET | `/communications/health` | health | Health check |

### Key Vaults

| Vault | Resource Group | Purpose |
|-------|----------------|---------|
| `acidni-keyvault` | `rg-dev` | Acidni shared secrets (IONOS API, etc.) |
| `kv-terprint` | `rg-dev-terprint-shared` | Terprint product secrets |

### DNS Domains (IONOS)

| Domain | Provider | Notes |
|--------|----------|-------|
| `acidni.net` | IONOS | Corporate domain, M365, Azure apps |
| `terprint.com` | IONOS | Product domain, sales site |
| `acidni.com` | NOT in IONOS | Check GoDaddy |

---

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
1. **Discovery**: Use Menu Discoverer to find API endpoint
2. **Validation**: Test API reliability, data quality
3. **Mapping**: Create field mappings (strain, terpene, cannabinoid extraction)
4. **Configuration**: Add to terprint-config package
5. **Testing**: Write unit tests for new mappings
6. **Integration**: Add to Menu Downloader configuration
7. **Monitoring**: Track data quality in Event House
8. **Documentation**: Update dispensary list in docs

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
- ✅ **Curaleaf**: Active (GrowerID 10)
- 🔴 **Sunnyside**: Discovery in progress

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

---

## Curaleaf Batch and Strain Name Mapping (2025-12-17)

**GrowerID:** 10

**Batch Name Mapping:**
- Formula: `{batch_number}`
- JSONPath: `$.products[*].batch_number`
- Fallback: `{sku}`

**Strain Name Mapping:**
- Formula: `{strain}`
- JSONPath: `$.products[*].strain`
- Fallback: `{name}`

**Integration Steps:**
1. Ensure menu-downloader and COA data extractor use the updated shared/dispensary-mappings.json.
2. For Curaleaf, extract batch and strain names using the above mapping logic.
3. Validate output using sample files and update tests/fixtures as needed.
4. Review and monitor for any unmapped or malformed batch/strain values in production data.

**Reference:** See shared/dispensary-mappings.json, shared/curaleaf-mapping.json for full mapping block and field details.
