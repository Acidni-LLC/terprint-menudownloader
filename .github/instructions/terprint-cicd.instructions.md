---
description: 'CI/CD standards for Terprint services using GitHub Actions - build, test, deploy patterns for Container Apps'
applyTo: '**/.github/workflows/*.yml,**/.github/workflows/*.yaml,**/azure-pipelines.yml'
---

# Terprint CI/CD Instructions

## [!] CRITICAL: GITHUB ACTIONS FOR ALL REPOS [!]

> **All Terprint repos use GitHub Actions for CI/CD**
> **NEVER use Azure Pipelines - GitHub Actions is the ONLY supported CI/CD platform**
> **Azure DevOps is used ONLY for work item tracking**
> **Deployment target: Azure Container Apps through APIM**

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GitHub Repository                             │
│                    (terprint-ai-chat, etc.)                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ push to main
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions Workflow                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  Lint    │ -> │  Test    │ -> │  Build   │ -> │  Push    │      │
│  │  (ruff)  │    │ (pytest) │    │ (Docker) │    │  (ACR)   │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼ deploy
┌─────────────────────────────────────────────────────────────────────┐
│                   Azure Container Apps                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  Dev (auto) │ -> │ Staging     │ -> │ Prod        │             │
│  │             │    │ (manual)    │    │ (approval)  │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

## Workflow Templates

### Option 1: Reusable Workflow (Recommended)

Call the centralized workflow from `terprint-config`:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'dev'
        type: choice
        options: [dev, staging, prod]

jobs:
  deploy:
    uses: Acidni-LLC/terprint-config/.github/workflows/reusable-deploy.yml@main
    with:
      app-name: 'ai-chat'  # Change to your app name
      environment: ${{ github.event.inputs.environment || 'dev' }}
    secrets: inherit
```

### Option 2: Full Workflow (Copy and Customize)

Copy from `terprint-config/.github/workflow-templates/container-app-deploy.yml`

## 🔐 Organization-Level Secrets (RECOMMENDED)

> **NEW:** We've migrated to organization-level secrets for better security and easier management.
> See [Organization Secrets Migration Guide](../../docs/ORGANIZATION_SECRETS_MIGRATION.md) for full details.

### Benefits

- ✅ **Single source of truth** - Update once, applies to all repos
- ✅ **Easier secret rotation** - Rotate credentials in one place
- ✅ **Reduced configuration** - New repos inherit org secrets automatically
- ✅ **Better security** - Fewer places secrets can leak

### Organization Secrets (Configured Once)

These are configured at the **Acidni-LLC organization level** and inherited by all repos using `secrets: inherit`:

| Secret Name | Description | Configured By |
|-------------|-------------|---------------|
| `ORG_AZURE_CREDENTIALS` | Azure Service Principal JSON | DevOps Team |
| `ORG_AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | DevOps Team |
| `ORG_AZURE_TENANT_ID` | Azure AD Tenant ID | DevOps Team |
| `ORG_ACR_USERNAME` | Azure Container Registry username | DevOps Team |
| `ORG_ACR_PASSWORD` | Azure Container Registry password | DevOps Team |
| `ORG_APIM_SUBSCRIPTION_KEY` | APIM gateway subscription key | DevOps Team |
| `ORG_GH_PAT_TERPRINT_TESTS` | PAT for triggering integration tests | DevOps Team |
| `ORG_AZURE_ARTIFACTS_TOKEN` | Azure DevOps Artifacts PAT | DevOps Team |

**Migration Status:** Track your repo's migration at [Organization Secrets Migration Guide](../../docs/ORGANIZATION_SECRETS_MIGRATION.md)

### Organization Variables (Non-Sensitive Config)

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `ORG_ACR_LOGIN_SERVER` | `crterprint.azurecr.io` | Primary ACR |
| `ORG_APIM_BASE_URL` | `https://apim-terprint-dev.azure-api.net` | APIM gateway |
| `ORG_PYTHON_VERSION` | `3.12` | Default Python version |

### Repository-Level Secrets (Deprecated)

> ⚠️ **DEPRECATED:** Repository-level secrets are being phased out. Use organization secrets instead.

If you haven't migrated yet, configure these in each repo's Settings > Secrets:

| Secret | Description | How to Get |
|--------|-------------|------------|
| `AZURE_CREDENTIALS` | Azure Service Principal JSON | `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_SUBSCRIPTION_ID` | Subscription ID | Azure Portal |
| `AZURE_TENANT_ID` | Tenant ID | Azure Portal |
| `ACR_USERNAME` | ACR admin username | `az acr credential show` |
| `ACR_PASSWORD` | ACR admin password | `az acr credential show` |
| `APIM_SUBSCRIPTION_KEY` | APIM subscription key | Key Vault |

### Setting Up AZURE_CREDENTIALS (Legacy - For Reference Only)

```bash
# ⚠️ DEPRECATED: Use ORG_AZURE_CREDENTIALS instead
# Create Service Principal for GitHub Actions
az ad sp create-for-rbac \
  --name "sp-github-terprint-{app-name}" \
  --role contributor \
  --scopes /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-shared \
  --sdk-auth

# Copy the JSON output to AZURE_CREDENTIALS secret
```

## Workflow Best Practices

### 1. Trigger Configuration

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - '**.md'
      - 'docs/**'
      - '.github/**'
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'dev'
```

### 2. Build Caching

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### 3. Test Before Deploy

```yaml
- name: Run tests
  run: |
    pip install pytest pytest-cov
    pytest tests/ -v --cov=src --cov-report=xml
  continue-on-error: false  # Fail the build if tests fail
```

### 4. Environment Promotion

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    # Build always runs

  deploy-dev:
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: dev
    # Auto-deploy to dev

  deploy-staging:
    needs: deploy-dev
    if: github.event.inputs.environment == 'staging'
    environment: staging
    # Manual trigger for staging

  deploy-prod:
    needs: deploy-staging
    if: github.event.inputs.environment == 'prod'
    environment: 
      name: prod
      url: https://apim-terprint.azure-api.net
    # Requires approval for prod
```

### 5. Health Verification

```yaml
- name: Verify deployment
  run: |
    sleep 45  # Wait for deployment
    
    for i in {1..5}; do
      response=$(curl -s -o /dev/null -w "%{http_code}" \
        "https://apim-terprint-dev.azure-api.net/${{ env.APP_NAME }}/api/health" \
        -H "Ocp-Apim-Subscription-Key: ${{ secrets.APIM_SUBSCRIPTION_KEY }}")
      
      if [ "$response" = "200" ]; then
        echo "✅ Health check passed"
        exit 0
      fi
      
      echo "Attempt $i: Status $response"
      sleep 10
    done
    
    echo "❌ Health check failed"
    exit 1
```

## Image Tagging Strategy

```yaml
- name: Extract metadata
  id: meta
  uses: docker/metadata-action@v5
  with:
    images: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}
    tags: |
      type=sha,prefix=${{ env.ENVIRONMENT }}-
      type=raw,value=${{ env.ENVIRONMENT }}-latest
      type=semver,pattern={{version}},enable=${{ github.ref_type == 'tag' }}
```

### Tag Examples

| Event | Tags Generated |
|-------|----------------|
| Push to main | `dev-abc1234`, `dev-latest` |
| Manual staging | `staging-abc1234`, `staging-latest` |
| Tag v1.2.3 | `1.2.3`, `1.2`, `1` |

## Container Registry

### ACR Details

| Property | Value |
|----------|-------|
| Registry | `acrterprintdev.azurecr.io` |
| Naming | `terprint-{service}:{env}-{sha}` |

### Pushing to ACR

```yaml
- name: Log in to ACR
  uses: azure/docker-login@v1
  with:
    login-server: acrterprintdev.azurecr.io
    username: ${{ secrets.ACR_USERNAME }}
    password: ${{ secrets.ACR_PASSWORD }}

- name: Build and push
  uses: docker/build-push-action@v5
  with:
    context: .
    push: true
    tags: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ env.ENVIRONMENT }}-${{ github.sha }}
```

## Deploying to Container Apps

### Using Azure CLI

```yaml
- name: Deploy to Container App
  uses: azure/container-apps-deploy-action@v1
  with:
    resourceGroup: rg-${{ env.ENVIRONMENT }}-terprint-shared
    containerAppName: ca-terprint-${{ env.APP_NAME }}
    imageToDeploy: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ env.ENVIRONMENT }}-${{ github.sha }}
```

### Using Azure CLI Directly

```yaml
- name: Deploy
  run: |
    az containerapp update \
      --name ca-terprint-${{ env.APP_NAME }} \
      --resource-group rg-${{ env.ENVIRONMENT }}-terprint-shared \
      --image acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ env.ENVIRONMENT }}-${{ github.sha }}
```

## Pull Request Checks

### PR Workflow

```yaml
name: PR Checks

on:
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install ruff
      - run: ruff check .

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest
      - run: pytest tests/unit -v

  build-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: docker build --target builder .  # Test build only
```

## Rollback Strategy

### Manual Rollback

```bash
# List recent images
az acr repository show-tags -n acrterprintdev --repository terprint-ai-chat --orderby time_desc --top 5

# Rollback to previous image
az containerapp update \
  --name ca-terprint-ai-chat \
  --resource-group rg-dev-terprint-shared \
  --image acrterprintdev.azurecr.io/terprint-ai-chat:dev-previous-sha
```

### Automated Rollback (On Health Check Failure)

```yaml
- name: Deploy with rollback
  run: |
    # Store current image
    CURRENT=$(az containerapp show -n ca-terprint-${{ env.APP_NAME }} -g rg-dev-terprint-shared --query properties.template.containers[0].image -o tsv)
    
    # Deploy new image
    az containerapp update -n ca-terprint-${{ env.APP_NAME }} -g rg-dev-terprint-shared --image $NEW_IMAGE
    
    # Health check
    sleep 45
    if ! curl -sf "https://apim-terprint-dev.azure-api.net/${{ env.APP_NAME }}/api/health" -H "Ocp-Apim-Subscription-Key: ${{ secrets.APIM_SUBSCRIPTION_KEY }}"; then
      echo "❌ Rolling back to $CURRENT"
      az containerapp update -n ca-terprint-${{ env.APP_NAME }} -g rg-dev-terprint-shared --image $CURRENT
      exit 1
    fi
```

## Notifications

### Slack Notification

```yaml
- name: Notify Slack
  if: always()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    fields: repo,message,commit,author,action,eventName,workflow
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

### GitHub Deployment Status

```yaml
- name: Create deployment
  uses: chrnorm/deployment-action@v2
  id: deployment
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    environment: ${{ env.ENVIRONMENT }}

- name: Update deployment status
  if: always()
  uses: chrnorm/deployment-status@v2
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    deployment-id: ${{ steps.deployment.outputs.deployment_id }}
    state: ${{ job.status }}
```

## Security Scanning

### Container Scanning

```yaml
- name: Scan image
  uses: aquasecurity/trivy-action@master
  with:
    image-ref: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ github.sha }}
    format: 'sarif'
    output: 'trivy-results.sarif'

- name: Upload scan results
  uses: github/codeql-action/upload-sarif@v2
  with:
    sarif_file: 'trivy-results.sarif'
```

### Dependency Scanning

```yaml
- name: Check dependencies
  run: |
    pip install pip-audit
    pip-audit --requirement requirements.txt
```

## Integration Testing (Terprint.Tests)

> **CRITICAL**: All deployments MUST trigger integration tests after successful deployment

### Test Dashboard

**Live Dashboard**: https://brave-stone-0d8700d0f.3.azurestaticapps.net

### Test Trigger Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Your App Repo (e.g., terprint-ai-chat)           │
│                                                                      │
│  deploy.yml:                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐              │
│  │  Build   │ -> │  Deploy  │ -> │ Trigger Tests    │              │
│  │          │    │  to CA   │    │ (repository_     │              │
│  │          │    │          │    │  dispatch)       │              │
│  └──────────┘    └──────────┘    └──────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                              │
                                              ▼ event: post-deploy-tests
┌─────────────────────────────────────────────────────────────────────┐
│                    terprint-tests Repository                         │
│                                                                      │
│  terprint-tests.yml:                                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐              │
│  │  Setup   │ -> │  Run All │ -> │ Upload Reports   │              │
│  │  Python  │    │  Tests   │    │ to Dashboard     │              │
│  └──────────┘    └──────────┘    └──────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### Adding Test Trigger to Your Workflow

Add this job to your deploy workflow (after successful deployment):

```yaml
# Add to .github/workflows/deploy.yml in your app repo
jobs:
  deploy:
    # ... your existing deploy job ...

  trigger-integration-tests:
    needs: deploy
    runs-on: ubuntu-latest
    if: success()
    steps:
      - name: Trigger Terprint Integration Tests
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.GH_PAT_TERPRINT_TESTS }}
          repository: Acidni-LLC/terprint-tests
          event-type: post-deploy-tests
          client-payload: |
            {
              "service": "${{ env.APP_NAME }}",
              "source_repo": "${{ github.repository }}",
              "deploy_run": "${{ github.run_id }}",
              "environment": "${{ env.ENVIRONMENT }}"
            }
```

### Required Secrets for Test Integration

| Secret | Where to Set | Description |
|--------|--------------|-------------|
| `GH_PAT_TERPRINT_TESTS` | Each app repo | PAT with `repo:dispatch` access to `Acidni-LLC/terprint-tests` |
| `APIM_SUBSCRIPTION_KEY` | terprint-tests repo | APIM key for API tests |
| `TERPRINT_BACKEND_API_KEY` | terprint-tests repo | Backend key for direct tests |

### Which Services Should Trigger Tests?

| Service | Trigger Tests | Reason |
|---------|---------------|--------|
| terprint-data-api | ✅ **Yes** | Core API - validates data endpoints |
| terprint-ai-chat | ✅ **Yes** | Customer-facing - APIM tests |
| terprint-ai-recommender | ✅ **Yes** | Customer-facing - APIM tests |
| terprint-ai-deals | ✅ **Yes** | Customer-facing - APIM tests |
| terprint-infographics | ✅ **Yes** | Customer-facing - APIM tests |
| terprint-ai-lab | ✅ **Yes** | Integration tests |
| terprint-metering | ✅ **Yes** | Billing validation critical |
| terprint-marketplace-webhook | ✅ **Yes** | Subscription tests |
| terprint-menudownloader | ⚠️ Optional | Data pipeline (health only) |
| terprint-batch-processor | ⚠️ Optional | Data pipeline (health only) |

### Viewing Test Results

| Resource | URL |
|----------|-----|
| **Test Dashboard** | https://brave-stone-0d8700d0f.3.azurestaticapps.net |
| **GitHub Actions** | https://github.com/Acidni-LLC/terprint-tests/actions |
| **Pipeline Artifacts** | Download from workflow run |

### Complete Workflow with Testing

```yaml
name: Deploy with Tests

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Target environment'
        default: 'dev'
        type: choice
        options: [dev, staging, prod]

env:
  APP_NAME: 'ai-chat'  # Change per repo
  ENVIRONMENT: ${{ github.event.inputs.environment || 'dev' }}

jobs:
  build:
    runs-on: ubuntu-latest
    outputs:
      image-tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to ACR
        uses: azure/docker-login@v1
        with:
          login-server: acrterprintdev.azurecr.io
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ env.ENVIRONMENT }}-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'dev' }}
    steps:
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Deploy to Container App
        uses: azure/container-apps-deploy-action@v1
        with:
          resourceGroup: rg-${{ env.ENVIRONMENT }}-terprint-shared
          containerAppName: ca-terprint-${{ env.APP_NAME }}
          imageToDeploy: acrterprintdev.azurecr.io/terprint-${{ env.APP_NAME }}:${{ env.ENVIRONMENT }}-${{ github.sha }}
      
      - name: Verify Deployment Health
        run: |
          sleep 45
          curl -sf "https://apim-terprint-${{ env.ENVIRONMENT }}.azure-api.net/${{ env.APP_NAME }}/api/health" \
            -H "Ocp-Apim-Subscription-Key: ${{ secrets.APIM_SUBSCRIPTION_KEY }}" \
            || (echo "❌ Health check failed" && exit 1)
          echo "✅ Deployment healthy"

  integration-tests:
    needs: deploy
    runs-on: ubuntu-latest
    if: success()
    steps:
      - name: Trigger Terprint Integration Tests
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.GH_PAT_TERPRINT_TESTS }}
          repository: Acidni-LLC/terprint-tests
          event-type: post-deploy-tests
          client-payload: |
            {
              "service": "${{ env.APP_NAME }}",
              "source_repo": "${{ github.repository }}",
              "deploy_run": "${{ github.run_id }}",
              "environment": "${{ env.ENVIRONMENT }}",
              "sha": "${{ github.sha }}"
            }
      
      - name: Post Test Dashboard Link
        run: |
          echo "## 🧪 Integration Tests Triggered" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "View results at: https://brave-stone-0d8700d0f.3.azurestaticapps.net" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "Test run triggered for service: **${{ env.APP_NAME }}**" >> $GITHUB_STEP_SUMMARY
```

---

## Repo Setup Checklist

For each Terprint service repo:

- [ ] Copy workflow from `terprint-config/.github/workflow-templates/`
- [ ] Configure GitHub Secrets (AZURE_CREDENTIALS, ACR_*, APIM_*)
- [ ] **Add `GH_PAT_TERPRINT_TESTS` secret for test triggering**
- [ ] Create GitHub Environments (dev, staging, prod)
- [ ] Set up branch protection on `main`
- [ ] Enable required status checks
- [ ] Configure production environment approvers
- [ ] Add Dockerfile using standard template
- [ ] **Add integration-tests job to workflow**
- [ ] Test workflow with manual trigger
- [ ] Verify tests run on dashboard after first deploy
