# Terprint AI Software Engineer & Architect Guidelines

**Version:** 2.1.18
**Last Updated:** January 20, 2026 19:18:00
**terprint-config Package Version:** 4.6.0

---

> **?? INHERITANCE**: This file contains comprehensive **Terprint-specific** instructions.
> It extends the **[Acidni Master Instructions](https://github.com/Acidni-LLC/terprint-config/blob/main/shared/acidni-copilot-instructions.md)** (`../terprint-config/shared/acidni-copilot-instructions.md`).
> See also: **[.github/instructions/](https://github.com/Acidni-LLC/terprint-config/tree/main/.github/instructions)** (`../terprint-config/.github/instructions/`) for technology-specific guidance.
> 
> **?? SYNC SCRIPT**: Run `copy-instructions-to-repos.ps1` to distribute this file to all Terprint repos.

---

## ?? Inherited From Acidni Master

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
- Poetry package management requirement

---

## ?? CRITICAL DIRECTIVES — ABSOLUTE RULES ??

> **These rules are MANDATORY. Violations will break the system.**

### DIRECTIVE 0: USE GITHUB ACTIONS FOR ALL CI/CD
- **ALL Terprint services use GitHub Actions for CI/CD** — NEVER use Azure Pipelines
- **GitHub is the source control AND CI/CD platform** — Azure DevOps is only for work item tracking
- **Deployment target**: Azure Container Apps through APIM gateway
- **Organization secrets**: Use ORG_* prefixed secrets and variables for consistency

### DIRECTIVE 1: REPOSITORY BOUNDARIES
- **EACH APP LIVES IN ITS OWN REPOSITORY** — Do NOT edit files in sibling repos
- **ALL CODE CHANGES ARE COORDINATED BY `terprint-config`** — Cross-cutting changes go through the config project  
- **CREATE AZURE DEVOPS WORK ITEMS** to track config changes needed across GitHub repos
- If you need changes in another repo, document the requirement and create a work item

> **IMPORTANT**: Repositories are hosted on **GitHub** (`github.com/Acidni-LLC`). Work items, project management, and artifacts are managed in **Azure DevOps** (`dev.azure.com/Acidni/Terprint`).

### DIRECTIVE 2: ALL PYTHON APPS MUST USE POETRY

> **MANDATORY: Poetry is the ONLY supported Python package manager for Terprint**

- **NEVER use `pip install` directly** — Always use `poetry add`
- **NEVER use `requirements.txt` as source of truth** — Use `pyproject.toml`
- **ALWAYS activate Poetry environment** before running Python code
- **Export requirements.txt for Docker** only when building containers

**Poetry Setup (New Project):**
```powershell
# Initialize new project
poetry init --name "terprint-myservice" --python "^3.12"

# Add dependencies
poetry add fastapi uvicorn azure-identity azure-storage-blob
poetry add --group dev pytest ruff mypy

# Install all dependencies
poetry install

# Activate environment
poetry shell
# OR run commands directly:
poetry run python main.py
poetry run pytest
```

**Poetry Setup (Existing Project):**
```powershell
# Install dependencies from pyproject.toml
poetry install

# Update lock file
poetry lock

# Activate and run
poetry shell
python main.py
```

**pyproject.toml Standard Structure:**
```toml
[tool.poetry]
name = "terprint-myservice"
version = "1.0.0"
description = "Terprint service description"
authors = ["Acidni LLC <dev@acidni.net>"]
readme = "README.md"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
azure-identity = "^1.15.0"
azure-storage-blob = "^12.19.0"
terprint-config = {version = "^4.0.0", source = "terprint"}

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
ruff = "^0.2.0"
mypy = "^1.8.0"

[[tool.poetry.source]]
name = "terprint"
url = "https://pkgs.dev.azure.com/Acidni/Terprint/_packaging/terprint/pypi/simple/"
priority = "supplemental"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
```

**Docker Integration with Poetry:**
```dockerfile
# Multi-stage build with Poetry
FROM python:3.12-slim AS builder
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1
RUN poetry config virtualenvs.create false

# Copy dependency files first (for layer caching)
COPY pyproject.toml poetry.lock ./

# Export to requirements.txt for production (without dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

FROM python:3.12-slim AS runtime
RUN groupadd -r terprint && useradd -r -g terprint terprint
WORKDIR /app

COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN chown -R terprint:terprint /app
USER terprint

ENV PYTHONUNBUFFERED=1 PORT=80
EXPOSE 80

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
```

**VS Code Settings for Poetry:**
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.analysis.typeCheckingMode": "strict"
}
```

**Migration Checklist (requirements.txt → Poetry):**
- [ ] Run `poetry init` in project root
- [ ] Add dependencies: `poetry add <package>` for each requirement
- [ ] Add dev dependencies: `poetry add --group dev <package>`
- [ ] Configure Azure Artifacts source for terprint-config
- [ ] Update Dockerfile to use Poetry export pattern
- [ ] Update CI/CD to use `poetry install` instead of `pip install`
- [ ] Remove requirements.txt (or keep only as generated export)
- [ ] Update .gitignore to include `.venv/` and `poetry.lock` (lock should be committed)

### DIRECTIVE 3: USE `pymssql` NOT `pyodbc` FOR SQL
- Azure Functions Consumption Plan runs on **Linux without ODBC drivers**
- `pyodbc` WILL FAIL in production
- Always use `pymssql` with `%s` placeholders (not `?`)

```python
# ✅ CORRECT - pymssql style
cursor.execute("SELECT * FROM Users WHERE Id = %s", (user_id,))

# ❌ WRONG - pyodbc style (will NOT work)
cursor.execute("SELECT * FROM Users WHERE Id = ?", (user_id,))
```

### DIRECTIVE 4: USE ENTRA ID FOR SERVICE-TO-SERVICE AUTH
- **NEVER use function keys** for app-to-app API calls
- **NEVER hard-code API keys** in source code
- **ALWAYS use managed identities** and Bearer tokens
- **ALWAYS validate token audience** to prevent reuse attacks

### DIRECTIVE 5: ALL INTER-SERVICE CALLS THROUGH APIM
- **ALL** API calls between Terprint services MUST route through APIM gateway
- **Base URL**: `https://apim-terprint-dev.azure-api.net`
- **NEVER** call function apps directly (e.g., `func-terprint-communications.azurewebsites.net`)

### DIRECTIVE 6: ALL SECRETS IN AZURE KEY VAULT
- **NEVER commit** API keys, connection strings, or passwords to source control
- **ALWAYS use** Key Vault references in Azure app settings: `@Microsoft.KeyVault(SecretUri=...)`
- **local.settings.json** is for local dev only and MUST be in `.gitignore`

### DIRECTIVE 7: GITHUB ACTIONS DEPLOYMENT WITH ORG SECRETS
- **ALL repositories MUST have GitHub Actions workflows** for deployment
- **USE ORGANIZATION SECRETS** (ORG_*) instead of repository secrets
- **TRIGGER integration tests** after successful deployment
- Test dashboard: https://brave-stone-0d8700d0f.3.azurestaticapps.net

**Required Workflow Pattern:**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to Azure
        uses: azure/login@v1
        with:
          creds: ${{ secrets.ORG_AZURE_CREDENTIALS }}
      
      - name: Login to ACR
        uses: docker/login-action@v3
        with:
          registry: ${{ vars.ORG_ACR_LOGIN_SERVER }}
          username: ${{ secrets.ORG_ACR_USERNAME }}
          password: ${{ secrets.ORG_ACR_PASSWORD }}
      
      - name: Build and Push Docker Image
        run: |
          docker build -t ${{ vars.ORG_ACR_LOGIN_SERVER }}/terprint-ai-chat:latest .
          docker push ${{ vars.ORG_ACR_LOGIN_SERVER }}/terprint-ai-chat:latest
      
      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name ca-terprint-ai-chat \
            --resource-group rg-dev-terprint-ca \
            --image ${{ vars.ORG_ACR_LOGIN_SERVER }}/terprint-ai-chat:latest
```

### DIRECTIVE 8: OPENAPI SPECS FOR ALL HTTP APIS
- Every Azure Function with HTTP triggers **MUST have `openapi.json`** in repo root
- Follow OpenAPI 3.0.x specification
- Include all endpoints, auth requirements, request/response schemas

### DIRECTIVE 9: MAINTAIN DOCUMENTATION
- Every repo **MUST have** `README.md`, `docs/ARCHITECTURE.md`, `docs/INTEGRATION.md`
- Keep docs in sync with code changes (update in same PR)
- Run `copy-instructions-to-repos.ps1` to distribute updated standards

### DIRECTIVE 10: BUSINESS LOGIC IN SHARED PACKAGES
- **Business logic belongs in `terprint-core`** packages (Python + NuGet)
- **Application code consumes** business logic, doesn't implement it

| Language | Package | Feed |
|----------|---------|------|
| Python | `terprint-core` | Azure Artifacts PyPI |
| .NET | `Terprint.Core` | Azure Artifacts NuGet |

### DIRECTIVE 11: SYSTEM VERSIONING & MULTI-TENANT ARCHITECTURE (V2.0)

> **Terprint Platform Version:** 2.0 (Multi-Tenant Architecture)  
> **terprint-config version:** 4.6.0  
> **Individual App Versions:** Track independently per repository

**System vs. App Versioning:**
- **Platform Version** (e.g., v2.0): Major architectural changes affecting all services
  - v1.0: Single-tenant architecture (legacy)
  - **v2.0**: Multi-tenant with CDES format, tenant isolation, tier-based access
- **App Version** (e.g., terprint-ai-chat v1.3.2): Individual service releases
  - Follow semantic versioning within each repository
  - Apps can be on different versions while sharing platform infrastructure

**V2 Multi-Tenant Requirements:**

| Feature | Implementation | Configuration |
|---------|---------------|---------------|
| **Tenant Context** | `TenantContext` from `terprint_config.v2` | `X-Tenant-ID`, `X-Tenant-Tier` headers |
| **API Format** | CDES (Cannabis Data Exchange Standard) | `V2Response` wrapper |
| **Data Isolation** | Tenant filtering in queries | Database row-level security |
| **Access Control** | Dispensary access by tier | See Tenant Tier Matrix below |
| **API Client** | `TerprintV2Client` for inter-service calls | Auto tenant propagation |

**Tenant Tier Access Matrix:**

| Tier | Dispensary Access | API Rate Limit | Metering |
|------|-------------------|----------------|----------|
| FREE | Demo only (ID 0) | 100/day | Tracked, not billed |
| STARTER | 2 dispensaries | 1000/day | Overage billing |
| PROFESSIONAL | 5 dispensaries | 10000/day | Overage billing |
| ENTERPRISE | All dispensaries | Unlimited | Custom contract |
| INTERNAL | All (admin) | Unlimited | Not metered |

**V2 Deployment Checklist:** See [V2_DEPLOYMENT_CHECKLIST.md](https://github.com/Acidni-LLC/terprint-config/blob/main/V2_DEPLOYMENT_CHECKLIST.md) (`../terprint-config/V2_DEPLOYMENT_CHECKLIST.md`)  
**V2 API Guide:** See [docs/V2_API_GUIDE.md](https://github.com/Acidni-LLC/terprint-config/blob/main/docs/V2_API_GUIDE.md) (`../terprint-config/docs/V2_API_GUIDE.md`)

### DIRECTIVE 12: APIM SUBSCRIPTION KEYS & METERING

> **CRITICAL**: All APIM subscription keys are managed in Azure Key Vault  
> **Reference Documentation**: [docs/API_MANAGER.md](https://github.com/Acidni-LLC/terprint-config/blob/main/docs/API_MANAGER.md) (`../terprint-config/docs/API_MANAGER.md`)

### DIRECTIVE 13: USE ORGANIZATION SECRETS FOR CI/CD

> **Migration Status**: ?? Ready for Implementation  
> **Reference Documentation**: [docs/ORGANIZATION_SECRETS_MIGRATION.md](https://github.com/Acidni-LLC/terprint-config/blob/main/docs/ORGANIZATION_SECRETS_MIGRATION.md) (`../terprint-config/docs/ORGANIZATION_SECRETS_MIGRATION.md`)  
> **Migration Tracking**: See migration table in terprint-config repo for repo-by-repo status

**ALL Terprint repositories MUST use GitHub Organization-level secrets instead of repository-level secrets.**

**Benefits:**
- **Single Source of Truth** - Update credentials once, applies to all repos
- **Easier Secret Rotation** - Rotate in one place instead of 50+ repos
- **Reduced Configuration** - New repos inherit org secrets automatically
- **Better Security** - Fewer places secrets can leak
- **Operational Excellence** - Aligns with Azure Well-Architected Framework

#### Organization Secrets (Prefix: `ORG_`)

| Secret Name | Description | How to Obtain |
|-------------|-------------|---------------|
| `ORG_AZURE_CREDENTIALS` | Azure Service Principal JSON | Create with `az ad sp create-for-rbac --sdk-auth` |
| `ORG_AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | `bb40fccf-9ffa-4bad-b9c0-ea40e326882c` |
| `ORG_AZURE_TENANT_ID` | Azure AD Tenant ID | `3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd` |
| `ORG_ACR_USERNAME` | Azure Container Registry username | `crterprint` |
| `ORG_ACR_PASSWORD` | Azure Container Registry password | From Key Vault or `az acr credential show` |
| `ORG_APIM_SUBSCRIPTION_KEY` | APIM gateway subscription key | From Key Vault `apim-subscription-key` |
| `ORG_GH_PAT_TERPRINT_TESTS` | PAT for triggering integration tests | GitHub Settings > Developer settings |
| `ORG_AZURE_ARTIFACTS_TOKEN` | Azure DevOps Artifacts PAT | Azure DevOps > Personal Access Tokens |

#### Organization Variables (Non-Sensitive Config)

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `ORG_ACR_LOGIN_SERVER` | `crterprint.azurecr.io` | Primary ACR |
| `ORG_APIM_BASE_URL` | `https://apim-terprint-dev.azure-api.net` | APIM gateway |
| `ORG_CONTAINER_ENV` | `kindmoss-c6723cbe.eastus2.azurecontainerapps.io` | Container Apps Environment |
| `ORG_PYTHON_VERSION` | `3.12` | Default Python version |
| `ORG_DOTNET_VERSION` | `8.0` | Default .NET version |

#### Workflow Pattern (Use Reusable Workflow)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    uses: Acidni-LLC/terprint-config/.github/workflows/reusable-deploy.yml@main
    with:
      app-name: 'ai-chat'
      environment: 'dev'
    secrets: inherit  # ✅ Inherits all ORG_* secrets automatically
```

#### Setting Organization Secrets (GitHub CLI)

```bash
# Set organization secrets
gh secret set ORG_AZURE_CREDENTIALS --org Acidni-LLC --body "$(cat azure-credentials.json)" --visibility all
gh secret set ORG_ACR_PASSWORD --org Acidni-LLC --body "$(az acr credential show --name crterprint --query 'passwords[0].value' -o tsv)" --visibility all
gh secret set ORG_APIM_SUBSCRIPTION_KEY --org Acidni-LLC --body "$(az keyvault secret show --vault-name kv-terprint-dev --name apim-subscription-key --query value -o tsv)" --visibility all

# Set organization variables
gh variable set ORG_ACR_LOGIN_SERVER --org Acidni-LLC --body "crterprint.azurecr.io" --visibility all
gh variable set ORG_PYTHON_VERSION --org Acidni-LLC --body "3.12" --visibility all
```

#### Migration Checklist

When migrating a repository to organization secrets:

- [ ] Update workflow to use `reusable-deploy.yml` with `secrets: inherit`
- [ ] Verify workflow runs successfully with org secrets
- [ ] Remove duplicate repository-level secrets:
  ```bash
  gh secret delete AZURE_CREDENTIALS --repo Acidni-LLC/{repo-name}
  gh secret delete ACR_USERNAME --repo Acidni-LLC/{repo-name}
  gh secret delete ACR_PASSWORD --repo Acidni-LLC/{repo-name}
  ```
- [ ] Update migration tracking table in `docs/ORGANIZATION_SECRETS_MIGRATION.md`
- [ ] Commit changes and verify CI/CD passes
- [ ] Run integration tests to confirm deployment works

#### Secret Rotation (Organization-Wide)

```bash
# ✅ New way - rotate once for all repos
gh secret set ORG_AZURE_CREDENTIALS --org Acidni-LLC --body "$(cat new-creds.json)" --visibility all

# ❌ Old way - update 50+ repos individually (NO LONGER NEEDED)
```

**Key Vault Secret Names:**
```
apim-subscription-key          # Primary APIM gateway key
svc-{service-name}-key         # Service-specific keys (e.g., svc-ai-chat-key)
```

**Access Pattern (PowerShell):**
```powershell
# Get APIM subscription key
$key = az keyvault secret show --vault-name kv-terprint-dev --name apim-subscription-key --query value -o tsv

# Use in API calls
$headers = @{"Ocp-Apim-Subscription-Key" = $key}
Invoke-RestMethod -Uri "https://apim-terprint-dev.azure-api.net/data/api/health" -Headers $headers
```

**Access Pattern (Python - from terprint-metering or any service):**
```python
from terprint_config.metering import UsageEvent, MeteringDimension
import os

# Record metered usage (automatically sent to terprint-metering)
event = UsageEvent(
    customer_id="customer-uuid",
    dimension=MeteringDimension.API_CALLS.value,
    quantity=1.0,
    api_name="terprint-data",
    operation_id="/v2/strains"
)

# Submit to metering service via APIM
import requests
response = requests.post(
    "https://apim-terprint-dev.azure-api.net/metering/api/record",
    headers={"Ocp-Apim-Subscription-Key": os.environ["APIM_SUBSCRIPTION_KEY"]},
    json=event.to_dict()
)
```

**Metering Dimensions:** All dimensions defined in `terprint_config/metering.py`
- Reference path: `terprint-config/terprint_config/metering.py`
- Marketplace config: `terprint-config/shared/marketplace-config.json`

**APIM Products (Subscription Tiers):**

| Product | Rate Limit | Quota | APIs Included |
|---------|------------|-------|---------------|
| Free Tier | 10 req/min | 100/day | Data API (read-only) |
| Starter | 60 req/min | 1,000/day | Data API, Chat |
| Professional | 300 req/min | 10,000/day | All APIs |
| Enterprise | 1,000 req/min | Unlimited | All APIs + SLA |

### DIRECTIVE 14: INCLUDE CONTAINER REVISION IN HEALTH CHECKS

> **MANDATORY**: Every Container App MUST include the running container revision in its health check response.

This enables:
- **Deployment verification**: Confirm the correct revision is running after deployment
- **Troubleshooting**: Quickly identify which revision is serving traffic
- **Rollback validation**: Verify rollbacks are complete

**Required Environment Variable:**
Azure Container Apps automatically sets `CONTAINER_APP_REVISION` environment variable.

**Python Implementation:**
```python
import os

@app.route(route="health", auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "service": "my-service",
            "version": "1.0.0",
            "revision": os.environ.get("CONTAINER_APP_REVISION", "local"),
            "timestamp": datetime.utcnow().isoformat()
        }),
        mimetype="application/json"
    )
```

**FastAPI Implementation:**
```python
import os
from datetime import datetime

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "my-service",
        "version": "1.0.0",
        "revision": os.environ.get("CONTAINER_APP_REVISION", "local"),
        "timestamp": datetime.utcnow().isoformat()
    }
```

**C# / .NET Implementation:**
```csharp
[Function("Health")]
public IActionResult Health([HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "health")] HttpRequest req)
{
    return new OkObjectResult(new
    {
        status = "healthy",
        service = "my-service",
        version = "1.0.0",
        revision = Environment.GetEnvironmentVariable("CONTAINER_APP_REVISION") ?? "local",
        timestamp = DateTime.UtcNow.ToString("o")
    });
}
```

### DIRECTIVE 15: INTEGRATION TEST TRIGGERING IS MANDATORY

> **CRITICAL**: ALL customer-facing services MUST trigger integration tests after deployment using the organization PAT secret.

**Why This Matters:**
- Validates deployment success through APIM gateway
- Catches configuration issues before customers are affected
- Provides automated rollback signals for failed deployments
- Required for maintaining deployment quality SLAs

**MANDATORY Requirements:**

1. **Use Organization Secret**: `${{ secrets.ORG_GH_PAT_TERPRINT_TESTS }}`
   -  **NEVER use repository-level PAT secrets** (causes "Resource not accessible" errors)
   -  **ALWAYS use ORG_GH_PAT_TERPRINT_TESTS** (organization-level secret with proper permissions)

2. **Add trigger-integration-tests job** to your deployment workflow
3. **Make it conditional on deployment success**: `if: success()`
4. **Pass deployment metadata** in client-payload for tracking

**Required Workflow Pattern:**

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      # ... your deployment steps ...

  trigger-integration-tests:
    needs: deploy
    runs-on: ubuntu-latest
    if: success()  # Only trigger if deployment succeeded
    steps:
      - name: Trigger Terprint Integration Tests
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.ORG_GH_PAT_TERPRINT_TESTS }}  #  MUST use org secret
          repository: Acidni-LLC/terprint-tests
          event-type: post-deploy-tests
          client-payload: |
            {
              "service": "${{ github.event.repository.name }}",
              "source_repo": "${{ github.repository }}",
              "deploy_run": "${{ github.run_id }}",
              "commit_sha": "${{ github.sha }}",
              "environment": "dev"
            }
```

**Services Requiring Integration Tests:**

| Service Type | Trigger Tests | Rationale |
|--------------|---------------|-----------|
| API Services (APIM) |  **REQUIRED** | Customer-facing - must validate APIM routing |
| AI Services |  **REQUIRED** | Customer-facing - critical functionality |
| Metering/Billing |  **REQUIRED** | Financial impact - must validate before live |
| Data Pipeline |  Optional | Internal - health check sufficient |

**Troubleshooting PAT Errors:**

If you see: `Resource not accessible by personal access token`

**Root Cause**: Using repository-level secret instead of organization secret

**Fix:**
```yaml
#  WRONG - causes PAT permission error
token: ${{ secrets.GH_PAT_TERPRINT_TESTS }}

#  CORRECT - uses org secret with proper permissions
token: ${{ secrets.ORG_GH_PAT_TERPRINT_TESTS }}
```

**Verification:**
- Test dashboard: https://brave-stone-0d8700d0f.3.azurestaticapps.net
- Check integration test runs in terprint-tests repository
- Verify your service appears in post-deployment test results

---

## ?? System Identity & Boundaries

| Property | Value |
|----------|-------|
| Platform Owner | Acidni LLC |
| Domain | Cannabis/Medical Marijuana Data Analytics |
| Geography | Florida dispensaries |
| Active Dispensaries | Cookies, M�V, Flowery, Trulieve, Curaleaf |
| Architecture | 5-stage data pipeline with microservices deployed as Azure Container Apps behind APIM |

---

## ?? Azure Well-Architected Framework Application

Apply these pillars to ALL architectural decisions:

| Pillar | Terprint Application |
|--------|---------------------|
| **Reliability** | Idempotent batch processing, retry policies with exponential backoff, health probes, circuit breakers |
| **Security** | Managed identities (no secrets in code), APIM gateway as single entry point, Key Vault for all secrets, zero-trust service-to-service auth via Entra ID |
| **Cost Optimization** | Consumption-based Container Apps, scale-to-zero patterns, right-sized SKUs |
| **Operational Excellence** | Centralized config (terprint-config), conventional commits, runbooks for incident response, DORA metrics tracking |
| **Performance Efficiency** | Response caching via APIM policies, async processing for long operations, blob storage for large payloads |

---

## ?? 5-Stage Pipeline Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Stage 1    │    │  Stage 2    │    │ Stage 2.5   │    │  Stage 3    │    │  Stage 4/5  │
│  Discovery  │ -> │  Ingestion  │ -> │   Batch     │ -> │    COA      │ -> │ Presentation│
│             │    │             │    │ Extraction  │    │ Processing  │    │ & Analytics │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     Manual         Every 2hrs         Daily 7AM         3x Daily           On-demand
                    8am-10pm EST                         9:30am/3:30pm
                                                         9:30pm
```

### Pipeline Stage Details

| Stage | Application | Type | Trigger | Output |
|-------|-------------|------|---------|--------|
| 1 - Discovery | Menu Discoverer | Development | Manual | DevOps work items |
| 2 - Ingestion | Menu Downloader | Container App | Every 2 hrs (8am-10pm EST) | Raw menu JSONs |
| 2.5 - Batch Extraction | Batch Creator | Container App | Daily 7:00 AM ET | `consolidated_batches_YYYYMMDD.json` |
| 3 - COA Processing | Batch Processor | Container App | 3x daily | SQL records |
| 4 - Presentation | Terprint.Web | App Service | On-demand | Web UI |
| 5 - Analytics | Power BI | Scheduled refresh | Daily | Reports + custom visuals |

---

## ??️ Service Catalog (All Terprint Components)

### AI Services

| Service | Repo | APIM Path | Local Port | Emoji |
|---------|------|-----------|------------|-------|
| AI Chat | terprint-ai-chat | `/chat` | 7091 | ?? |
| AI Recommender | terprint-ai-recommender | `/recommend` | 7096 | ?? |
| AI Deals | terprint-ai-deals | `/deals` | 7101 | ?? |
| AI Lab | terprint-ai-lab | `/lab` | 7126 | ?? |
| AI Health | terprint-ai-health | `/health` | 7106 | ?? |

### Data Processing Pipeline

| Service | Repo | APIM Path | Local Port | Emoji |
|---------|------|-----------|------------|-------|
| Menu Downloader | terprint-menudownloader | `/menus` | 7086 | ?? |
| Batch Creator | terprint-batches | `/batches` | 7076 | ?? |
| Batch Processor | terprint-batch-processor | `/processor` | 7081 | ?? |
| COA Extractor | terprint-coa-extractor | `/coa` | 7131 | ?? |
| Data API | terprint-data | `/data` | 7121 | ?? |

### Communications & Notifications

| Service | Repo | APIM Path | Local Port | Emoji |
|---------|------|-----------|------------|-------|
| Communications | terprint-communications | `/communications` | 7071 | ?? |

### Core Platform

| Component | Repo | Type | Description |
|-----------|------|------|-------------|
| terprint-config | terprint-config | Python Package | Central configuration (PyPI) - source of truth |
| Terprint.Web | Terprint.Web | .NET Blazor | Main website |
| Terprint.Tests | terprint-tests | .NET Tests | Integration test suite |

---

## ?? Azure Resources Reference

### Core Infrastructure

> ⚠️ **DO NOT GUESS RESOURCE GROUPS** - Each resource has a specific RG. Always reference this table.

| Resource Type | Name | Resource Group |
|---------------|------|----------------|
| Storage Account | `stterprintsharedgen2` | rg-dev-terprint-shared |
| Container | `jsonfiles` | (within storage account) |
| APIM | `apim-terprint-dev` | **rg-terprint-apim-dev** |
| Key Vault | `kv-terprint-dev` | rg-dev-terprint-shared |
| Container Registry | `crterprint.azurecr.io` | rg-dev-terprint-health |
| Container Apps Environment | `kindmoss-c6723cbe.eastus2.azurecontainerapps.io` | rg-dev-terprint-ca |
| Cosmos DB | `cosmos-terprint-dev` | rg-dev-terprint-shared |

### Cosmos DB Databases & Containers

Cosmos DB is used for AI service state management, user preferences, and metering data where document-oriented storage with low-latency reads is beneficial.

| Database | Container | Purpose |
|----------|-----------|---------|
| **TerprintAI** | `chat_sessions` | AI Chat conversation history and context |
| **TerprintAI** | `recommendations` | Cached strain recommendations |
| **TerprintAI** | `user_preferences` | User taste profiles and preferences |
| **TerprintAI** | `feedback` | User feedback on recommendations |
| **TerprintAI** | `strains` | Strain embeddings and metadata cache |
| **TerprintAI** | `menus` | Menu data cache for AI queries |
| **TerprintAI** | `ai_deals_*` | AI Deals service state (alerts, prices, notifications) |
| **TerprintAI** | `quality_alerts` | Data quality alerting |
| **TerprintAI** | `dispensary_reports` | Dispensary analytics cache |
| **terprint-metering** | `usage-events` | Raw API usage events |
| **terprint-metering** | `usage-aggregates` | Aggregated usage by customer/period |
| **terprint-metering** | `customer-quotas` | Customer tier quotas and limits |

**Access Pattern:**
```python
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

# Use managed identity (NEVER connection strings)
credential = DefaultAzureCredential()
client = CosmosClient("https://cosmos-terprint-dev.documents.azure.com:443/", credential)
db = client.get_database_client("TerprintAI")
container = db.get_container_client("chat_sessions")
```

### Azure Identifiers

| Property | Value |
|----------|-------|
| Tenant ID | `3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd` |
| Subscription ID | `bb40fccf-9ffa-4bad-b9c0-ea40e326882c` |
| DevOps Organization | `Acidni` |
| DevOps Project | `Terprint` |

### Container Registries (Use Correct ACR!)

| Registry Login Server | Purpose |
|-----------------------|---------|
| `crterprint.azurecr.io` | **PRIMARY** - Main Terprint services |
| `acrterprint7py7rei2pjnwq.azurecr.io` | AI Deals service |
| `caad4cae72c4acr.azurecr.io` | Doctor Portal |

### Blob Storage Structure

```
jsonfiles/
├── dispensaries/                    # Raw menu downloads (Stage 2 output)
│   ├── cookies/{year}/{month}/{day}/{timestamp}.json
│   ├── muv/...
│   ├── flowery/...
│   ├── trulieve/...
│   └── curaleaf/...
├── menus/                           # Processed menu data
│   └── {dispensary}/{year}/{month}/{day}/*.json
└── batches/                         # Consolidated batch files (Stage 2.5 output)
    └── consolidated_batches_YYYYMMDD.json
```

### Container Apps (All Terprint Services)

> **Note:** All Terprint services run as Azure Container Apps. Legacy Function Apps have been migrated.

| Container App | Resource Group | Purpose |
|--------------|----------------|---------|
| `ca-terprint-ai-chat` | `rg-dev-terprint-ca` | AI Chat service |
| `ca-terprint-menudownloader` | `rg-dev-terprint-ca` | Menu data ingestion |
| `ca-terprint-ai-recommender` | `rg-dev-terprint-ca` | Strain recommendations |
| `ca-terprint-batch-processor` | `rg-dev-terprint-ca` | COA data extraction |
| `ca-terprint-batches` | `rg-dev-terprint-ca` | Batch file creator |
| `ca-terprint-data` | `rg-dev-terprint-ca` | Data access API |
| `ca-terprint-ai-deals` | `rg-dev-terprint-ca` | Deal analysis |
| `ca-terprint-infographics` | `rg-dev-terprint-ca` | Infographic image generation |

### Legacy Function Apps (To Be Migrated)

> **Migration Target:** Move all remaining Function Apps to Container Apps

| Function App | Status | Notes |
|--------------|--------|-------|
| `func-terprint-marketplace` | ⚠️ Pending | Migrate to Container App |
| `func-terprint-metering` | ⚠️ Pending | Migrate to Container App |
| `func-terprint-coadataextractor` | ⚠️ Pending | Migrate to Container App |

### Static Web Apps

| App | Hostname | Purpose |
|-----|----------|---------|
| `swa-terprint-sales` | `green-forest-02ff0c80f.3.azurestaticapps.net` | Sales website (sales.terprint.com) |
| `swa-terprint-tests-dev` | `brave-stone-0d8700d0f.3.azurestaticapps.net` | Test dashboard |

---

## ?? APIM API Catalog

**Base URL**: `https://apim-terprint-dev.azure-api.net`

| API ID | Path | Backend | Caching |
|--------|------|---------|---------|
| `terprint-communications` | `/communications` | func-terprint-communications | 60s |
| `terprint-ai-chat-api` | `/chat` | func-dev-terprint-ai-chat | 300s |
| `terprint-ai-recommender-api` | `/recommend` | func-terprint-ai-recommender | 600s |
| `terprint-data-api` | `/data` | func-terprint-data-api | 300s |
| `terprint-infographics` | `/infographics` | func-terprint-infographics | 86400s |
| `terprint-stock-api` | `/stock` | terprint-menu-downloader | 3600s |

### Communications API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/communications/send-email` | Send email via Azure Communication Services |
| POST | `/communications/send-sms` | Send SMS via Azure Communication Services |
| POST | `/communications/send-batch-notification` | Batch notifications |
| GET | `/communications/health` | Health check |

### Python APIM Client Pattern

```python
import os
import requests

class TerprintAPIClient:
    """Client for calling Terprint services through APIM."""
    
    def __init__(self):
        self.base_url = os.environ.get("APIM_GATEWAY_URL", "https://apim-terprint-dev.azure-api.net")
        self.subscription_key = os.environ.get("APIM_SUBSCRIPTION_KEY")
        
    def _get_headers(self) -> dict:
        return {
            "Ocp-Apim-Subscription-Key": self.subscription_key,
            "Content-Type": "application/json"
        }
    
    def call_ai_chat(self, message: str, session_id: str = None) -> dict:
        response = requests.post(
            f"{self.base_url}/chat/api/chat",
            headers=self._get_headers(),
            json={"message": message, "session_id": session_id}
        )
        response.raise_for_status()
        return response.json()
```

---

## ?? Container App Standards

### Container App Naming Convention

```
ca-terprint-{service-name}
```

### Dockerfile Standards (Python Services with Poetry)

```dockerfile
# Multi-stage build with Poetry
FROM python:3.12-slim AS builder
WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1
RUN poetry config virtualenvs.create false

# Copy dependency files first (for layer caching)
COPY pyproject.toml poetry.lock ./

# Export to requirements.txt for production (without dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes --without dev

FROM python:3.12-slim AS runtime
RUN groupadd -r terprint && useradd -r -g terprint terprint
WORKDIR /app

# Install production dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

RUN chown -R terprint:terprint /app
USER terprint

ENV PYTHONUNBUFFERED=1 PORT=80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
```

### Required Health Endpoint

> **STANDARD PATH**: All Terprint services use `/health` (NOT `/api/health`)

Every Container App MUST expose:

```
GET /health
```

Response (200 OK):
```json
{
  "status": "healthy",
  "service": "ai-chat",
  "version": "1.2.3",
  "revision": "ca-terprint-ai-chat--abc123",
  "timestamp": "2026-01-07T12:00:00Z"
}
```

> **IMPORTANT**: The `revision` field is **MANDATORY** - see **DIRECTIVE 14**. Use `os.environ.get("CONTAINER_APP_REVISION", "local")` in Python or `Environment.GetEnvironmentVariable("CONTAINER_APP_REVISION")` in C#.

---

## ?? CI/CD Standards (GitHub Actions with Organization Secrets)

> **?? Comprehensive CI/CD Guide**: For complete CI/CD standards including deployment workflows, rollback strategies, security scanning, and integration testing, see **[terprint-cicd.instructions.md](https://github.com/Acidni-LLC/terprint-config/blob/main/.github/instructions/terprint-cicd.instructions.md)** (`../terprint-config/.github/instructions/terprint-cicd.instructions.md`)

**ALL Terprint repositories MUST use GitHub Actions workflows with organization secrets for deployment.**

### Standard Workflow Structure

Every repo needs `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.ORG_AZURE_CREDENTIALS }}

      - name: Setup Python (if Python app)
        uses: actions/setup-python@v4
        with:
          python-version: ${{ vars.ORG_PYTHON_VERSION }}

      - name: Install Poetry (if Python app)
        run: pip install poetry

      - name: Install dependencies (if Python app)
        run: poetry install --without dev

      - name: Build Docker image
        run: |
          docker build -t ${{ vars.ORG_ACR_LOGIN_SERVER }}/your-app:${{ github.sha }} .

      - name: Login to ACR
        uses: docker/login-action@v3
        with:
          registry: ${{ vars.ORG_ACR_LOGIN_SERVER }}
          username: ${{ secrets.ORG_ACR_USERNAME }}
          password: ${{ secrets.ORG_ACR_PASSWORD }}

      - name: Push Docker image
        run: |
          docker push ${{ vars.ORG_ACR_LOGIN_SERVER }}/your-app:${{ github.sha }}

      - name: Deploy to Container Apps
        run: |
          az containerapp update \
            --name ca-your-app \
            --resource-group rg-dev-terprint-ca \
            --image ${{ vars.ORG_ACR_LOGIN_SERVER }}/your-app:${{ github.sha }}
```

### Organization Secrets Usage

**✅ CORRECT - Use organization secrets:**
```yaml
with:
  creds: ${{ secrets.ORG_AZURE_CREDENTIALS }}  # From organization
  registry: ${{ vars.ORG_ACR_LOGIN_SERVER }}   # From organization variables
```

**❌ WRONG - Don't use repo secrets:**
```yaml
with:
  creds: ${{ secrets.AZURE_CREDENTIALS }}     # Old way - don't use
```

### Deployment Process

1. **Developer**: Push code to GitHub repo (`main` branch)
2. **GitHub Actions**: Workflow triggers automatically
3. **Build**: Docker image built using organization secrets
4. **Push**: Image pushed to ACR using `ORG_ACR_*` secrets
5. **Deploy**: Container App updated with new image
6. **Test**: Integration tests can be triggered via API call

---

## ?? Authentication Patterns

### Entra ID App-to-App Authentication

```python
from terprint_config.auth import get_auth_header, validate_token
import os

# Outbound: Get token for calling another service
headers = get_auth_header("func-terprint-communications")
response = requests.post(url, headers=headers, json=data)

# Inbound: Validate incoming tokens
result = validate_token(
    request.headers.get("Authorization"),
    expected_audience=os.environ["AZURE_CLIENT_ID"],
    required_scopes=["Communications.Send"]
)
if not result.valid:
    return {"error": result.error}, 401
```

### App Registration Names

| App | Application ID URI | Primary Scopes |
|-----|-------------------|----------------|
| `func-terprint-communications` | `api://func-terprint-communications` | Communications.Send, Communications.Read |
| `terprint-batches` | `api://terprint-batches` | BatchCreator.Process, BatchCreator.Backfill |
| `terprint-batch-processor` | `api://terprint-batch-processor` | COAProcessor.Execute, COAProcessor.Read |
| `func-terprint-menudownloader` | `api://func-terprint-menudownloader` | MenuDownloader.Download, MenuDownloader.StockCheck |
| `func-terprint-ai-chat` | `api://func-terprint-ai-chat` | AIChat.Query, AIChat.History |

---

## ??️ Operational Commands

### Service Health Verification

> **STANDARD PATH**: Health endpoints are at `/health` (NOT `/api/health`)

```powershell
# Check all services through APIM
$key = (az keyvault secret show --vault-name kv-terprint-dev --name apim-subscription-key --query value -o tsv)
$services = @("chat", "data", "recommend", "communications", "stock")
foreach ($svc in $services) {
    $url = "https://apim-terprint-dev.azure-api.net/$svc/health"
    try {
        $result = Invoke-RestMethod -Uri $url -Headers @{"Ocp-Apim-Subscription-Key"=$key}
        Write-Host "✅ $svc: $($result.status)" -ForegroundColor Green
    } catch {
        Write-Host "❌ $svc: FAILED" -ForegroundColor Red
    }
}
```

### Trigger Pipeline Stages Manually

```powershell
# Stage 2.5: Batch Creator
Invoke-RestMethod -Uri "https://ca-terprint-batches.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/trigger" `
    -Method POST -Body '{"preset": "today"}' -ContentType "application/json"

# Stage 2.5: Batch Creator (specific date backfill)
Invoke-RestMethod -Uri "https://ca-terprint-batches.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/trigger" `
    -Method POST -Body '{"date": "2026-01-17"}' -ContentType "application/json"

# Stage 3: Batch Processor
Invoke-RestMethod -Uri "https://ca-terprint-batchprocessor.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/run-batch-processor" `
    -Method POST -Body '{"date": "2026-01-17"}' -ContentType "application/json"
```

### Blob Storage Operations

```powershell
# List dispensary folders
az storage blob list --account-name stterprintsharedgen2 --container-name jsonfiles `
    --prefix "dispensaries/" --auth-mode login -o table

# Check if batch file exists
az storage blob exists --account-name stterprintsharedgen2 --container-name jsonfiles `
    --name "batches/consolidated_batches_20260117.json" --auth-mode login

# Download a menu file
az storage blob download --account-name stterprintsharedgen2 --container-name jsonfiles `
    --name "dispensaries/curaleaf/2026/01/07/menu.json" --file ./menu.json --auth-mode login
```

### Container App Management

```powershell
# View logs (follow mode)
az containerapp logs show --name ca-terprint-batches --resource-group rg-dev-terprint-ca --follow

# Restart current revision
$revision = (az containerapp revision list --name ca-terprint-batches --resource-group rg-dev-terprint-ca --query "[0].name" -o tsv)
az containerapp revision restart --name ca-terprint-batches --resource-group rg-dev-terprint-ca --revision $revision

# Update to latest image
az containerapp update --name ca-terprint-batches --resource-group rg-dev-terprint-ca `
    --image crterprint.azurecr.io/terprint-batches:latest
```

### Docker Build and Push

```powershell
# Login to Azure Container Registry
az acr login --name crterprint

# Build image
docker build -t crterprint.azurecr.io/terprint-batches:latest .

# Push to ACR
docker push crterprint.azurecr.io/terprint-batches:latest
```

### Local Development with Poetry

```powershell
# Start a service locally
$Host.UI.RawUI.WindowTitle = "?? Batch Creator (7076)"
cd terprint-batches
poetry install
poetry run uvicorn src.main:app --port 7076 --reload

# Run tests
poetry run pytest tests/ -v

# Run linting
poetry run ruff check .
poetry run mypy src/
```

---

## ?? Troubleshooting Runbooks

### Runbook: Pipeline Data Gap

**Symptom:** No data for a specific date in the database

**Resolution Steps:**

1. **Check Menu Downloader ran:**
   ```powershell
   az containerapp logs show --name ca-terprint-menudownloader --resource-group rg-dev-terprint-ca --tail 100
   ```

2. **Verify raw files exist:**
   ```powershell
   az storage blob list --account-name stterprintsharedgen2 --container-name jsonfiles `
       --prefix "dispensaries/cookies/2026/01/17/" --auth-mode login -o table
   ```

3. **Check Batch Creator output:**
   ```powershell
   az storage blob exists --account-name stterprintsharedgen2 --container-name jsonfiles `
       --name "batches/consolidated_batches_20260117.json" --auth-mode login
   ```

4. **Manual recovery - trigger each stage:**
   ```powershell
   # Re-run Batch Creator for specific date
   Invoke-RestMethod -Uri "https://ca-terprint-batches.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/trigger" `
       -Method POST -Body '{"date": "2026-01-17"}' -ContentType "application/json"
   ```

### Runbook: Service Health Failure

**Symptom:** APIM returns 5xx errors for a service

1. **Check Container App status:**
   ```powershell
   az containerapp show --name ca-terprint-batches --resource-group rg-dev-terprint-ca --query "properties.runningStatus"
   ```

2. **View recent logs:**
   ```powershell
   az containerapp logs show --name ca-terprint-batches --resource-group rg-dev-terprint-ca --tail 200
   ```

3. **Restart if needed:**
   ```powershell
   $revision = (az containerapp revision list --name ca-terprint-batches --resource-group rg-dev-terprint-ca --query "[0].name" -o tsv)
   az containerapp revision restart --name ca-terprint-batches --resource-group rg-dev-terprint-ca --revision $revision
   ```

---

## ??️ Local Development Ports

| App | Default Port | Window Title |
|-----|--------------|--------------|
| Communications | 7071 | ?? Communications |
| Batch Creator | 7076 | ?? Batch Creator |
| COA Processor | 7081 | ?? COA Processor |
| Menu Downloader | 7086 | ?? Menu Downloader |
| AI Chat | 7091 | ?? AI Chat |
| AI Recommender | 7096 | ?? AI Recommender |
| AI Deals | 7101 | ?? AI Deals |
| AI Health | 7106 | ?? AI Health |
| Infographics | 7111 | ?? Infographics |
| Metering | 7116 | ?? Metering |
| Data API | 7121 | ?? Data API |

**Starting an App Locally:**
```powershell
$Host.UI.RawUI.WindowTitle = "?? Communications (7071)"
func host start --port 7071
```

---

## ?? Dispensary Configuration

| Dispensary | Grower ID | Status | Notes |
|------------|-----------|--------|-------|
| Cookies | 1 | ✅ Active | Stable |
| M�V | 2 | ✅ Active | Stable |
| Flowery | 3 | ✅ Active | All FL locations |
| Trulieve | 4 | ✅ Active | 162 stores, 4 categories |
| Curaleaf | 10 | ✅ Active | ~45-60 stores |
| Sunnyside | 5 | ?? Discovery | In progress |
| Liberty | 6 | ?? Discovery | Planned |
| Fluent | 7 | ?? Discovery | Planned |
| VidaCann | 8 | ?? Discovery | Planned |
| RISE | 9 | ?? Discovery | Planned |

---

## ?? Testing Framework

> **?? Detailed CI/CD & Testing Instructions**: For comprehensive testing, deployment workflows, and integration test patterns, see **[terprint-cicd.instructions.md](https://github.com/Acidni-LLC/terprint-config/blob/main/.github/instructions/terprint-cicd.instructions.md)** (`../terprint-config/.github/instructions/terprint-cicd.instructions.md`)

### Testing Pyramid

| Level | Coverage | What to Test |
|-------|----------|--------------|
| Unit Tests | 70% | Dispensary parsers, field mappings, COA extraction |
| Integration Tests | 20% | Pipeline flow, Event House ingestion |
| E2E Tests | 10% | Full pipeline, website queries |

### Domain-Specific Testing
- **API Contract Tests**: Verify dispensary API responses match expected schema
- **Data Quality Tests**: Validate terpene percentages sum correctly
- **Idempotency Tests**: Ensure reprocessing doesn't create duplicates
- **Resilience Tests**: Test behavior when dispensary APIs are down
### Integration Test Trigger (REQUIRED)

> ** See DIRECTIVE 15 for complete requirements and troubleshooting**

> **CRITICAL**: ALL deployments MUST trigger integration tests after successful deployment

**Test Dashboard**: https://brave-stone-0d8700d0f.3.azurestaticapps.net

Every GitHub Actions workflow MUST include this job after deployment:

```yaml
trigger-integration-tests:
  needs: deploy
  runs-on: ubuntu-latest
  if: success()
  steps:
    - name: Trigger Terprint Integration Tests
      uses: peter-evans/repository-dispatch@v3
      with:
        token: ${{ secrets.ORG_GH_PAT_TERPRINT_TESTS }}  #  Organization secret (NOT repo secret)
        repository: Acidni-LLC/terprint-tests
        event-type: post-deploy-tests
        client-payload: |
          {
            "service": "${{ github.event.repository.name }}",
            "source_repo": "${{ github.repository }}",
            "deploy_run": "${{ github.run_id }}",
            "commit_sha": "${{ github.sha }}",
            "environment": "dev"
          }
```

>  **Common Error**: `Resource not accessible by personal access token`  
> **Cause**: Using repository secret instead of `ORG_GH_PAT_TERPRINT_TESTS` organization secret  
> **Fix**: Ensure you're using `secrets.ORG_GH_PAT_TERPRINT_TESTS` (org-level) not a repo-level PAT

---

## ?? DORA Metrics Targets

| Metric | Current | Target |
|--------|---------|--------|
| Deployment Frequency | Weekly | 2-3x per week |
| Lead Time for Changes | ~8 hours | < 4 hours |
| Change Failure Rate | ~10% | < 5% |
| Mean Time to Recovery | ~4 hours | < 2 hours |

---

## ✅ Code Review Checklist

Before approving any PR, verify:

- [ ] Uses Poetry for Python dependency management
- [ ] Uses `terprint_config.settings` for ALL configuration values
- [ ] All service calls route through APIM gateway
- [ ] No hardcoded secrets, API keys, or connection strings
- [ ] Uses `pymssql` (not `pyodbc`) for SQL connections
- [ ] Function auth level is `function` (not `anonymous`)
- [ ] Managed identity used for Azure resource access
- [ ] Tests added/updated for new functionality
- [ ] Documentation updated in same PR
- [ ] Conventional commit message format used

---

## ?? Conventional Commit Format

```
feat(batch-creator): add retry logic for blob storage failures
fix(menu-downloader): handle null terpene values in Curaleaf response
docs(readme): update deployment instructions for Container Apps
chore(deps): bump terprint-config to v4.5.0
test(coa-processor): add fixtures for Curaleaf menu format
refactor(ai-chat): extract embedding logic to shared module
```

---

## ?? Quick Reference Links

| Resource | URL |
|----------|-----|
| Azure DevOps | https://dev.azure.com/Acidni/Terprint |
| APIM Gateway | https://apim-terprint-dev.azure-api.net |
| Test Dashboard | https://brave-stone-0d8700d0f.3.azurestaticapps.net |
| Sales Site | https://sales.terprint.com |
| Main Web App | https://terprint.acidni.net |
| Container Registry | crterprint.azurecr.io |
| Key Vault | https://kv-terprint-dev.vault.azure.net |
| Storage Account | https://stterprintsharedgen2.blob.core.windows.net/jsonfiles |

---

## ?? Key Reminders

- **Data Accuracy is Critical**: Cannabis patients rely on accurate terpene/cannabinoid data
- **Dispensary APIs Change Often**: Build resilient, flexible parsers
- **Azure Managed Identities**: Never hardcode credentials
- **Domain Knowledge Matters**: Understand cannabis terminology (strain types, terpene effects, COA interpretation)
- **Quality Over Speed**: Accurate data > fast but wrong data
- **Idempotency**: The consolidated batch file is overwritten throughout the day—Batch Processor runs multiple times to catch updates
- **Poetry for Python**: All Python apps must use Poetry for dependency management

---

## ?? Sync Instructions to All Repos

To distribute this file to all Terprint repositories, run:

```powershell
# From terprint-config repo root
.\copy-instructions-to-repos.ps1
```

This copies `.github/copilot-instructions.md` to:
- terprint-ai-chat
- terprint-ai-recommender
- terprint-ai-deals
- terprint-coa-extractor
- terprint-batch-processor
- terprint-powerbi-visuals
- Terprint.Web
- Terprint.Tests
- func-terprint-communications
- terprint-ai-health
- And more...

















