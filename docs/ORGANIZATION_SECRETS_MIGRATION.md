# GitHub Organization Secrets Migration Guide

**Version:** 1.0.1  
**Last Updated:** January 19, 2026 19:20:00 EST  
**Status:** 🚀 Ready for Implementation

**Organization Secrets:** ✅ **SETUP COMPLETE** (7 secrets + 5 variables configured)

---

## 📋 Migration Tracking Table

> **INSTRUCTIONS:** When you migrate a repository, update this table and commit to `terprint-config`.
> Then run `.\copy-instructions-to-repos.ps1` to distribute updates to all repos.

| Repository | Status | Migrated By | Date | Workflow Updated | Secrets Removed | Notes |
|------------|--------|-------------|------|------------------|-----------------|-------|
| terprint-config | ✅ Complete | - | 2026-01-19 | N/A (master repo) | N/A | Contains reusable workflow |
| terprint-ai-chat | 🔄 In Progress | - | - | ⬜ No | ⬜ No | - |
| terprint-ai-recommender | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-ai-deals | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-ai-lab | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-ai-health | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-data | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-communications | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-menudownloader | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-batches | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-batch-processor | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-coa-extractor | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-infographics | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| acidni-publisher-portal | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-metering | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-stock-api | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| Terprint.Web | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-tests | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-doctor-portal | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |
| terprint-powerbi-visuals | ⬜ Not Started | - | - | ⬜ No | ⬜ No | - |

**Status Legend:**
- ⬜ Not Started
- 🔄 In Progress
- ✅ Complete
- ⚠️ Blocked (see Notes)
- ❌ Failed (see Notes)

**How to Update This Table:**
1. Find your repository in the table
2. Update Status, Migrated By (your name), Date
3. Check workflow updated and secrets removed boxes (✅ Yes / ⬜ No)
4. Add any notes (blockers, issues, etc.)
5. Commit changes to `terprint-config/docs/ORGANIZATION_SECRETS_MIGRATION.md`
6. Run `.\copy-instructions-to-repos.ps1` to sync to all repos

---

## Overview

This guide describes the migration from **repository-level secrets** to **organization-level secrets and variables** for Acidni LLC's Terprint platform. This aligns with Azure Well-Architected Framework's **Operational Excellence** pillar.

## Benefits of Organization-Level Secrets

| Benefit | Impact |
|---------|--------|
| **Single Source of Truth** | Update once, applies to all repos |
| **Easier Secret Rotation** | Rotate credentials in one place |
| **Reduced Configuration** | New repos inherit org secrets automatically |
| **Better Security** | Fewer places secrets can leak |
| **Audit Trail** | Centralized access logs |
| **Cost Efficiency** | Less time managing duplicate secrets |

---

## Architecture

### Before (Repository-Level)

```
┌────────────────────┐
│  terprint-ai-chat  │ ──► AZURE_CREDENTIALS (repo secret)
└────────────────────┘     ACR_USERNAME (repo secret)
                           ACR_PASSWORD (repo secret)

┌────────────────────┐
│  terprint-data     │ ──► AZURE_CREDENTIALS (repo secret)
└────────────────────┘     ACR_USERNAME (repo secret)
                           ACR_PASSWORD (repo secret)

❌ Problem: 50+ repos × 8 secrets = 400 duplicated secrets
```

### After (Organization-Level)

```
┌─────────────────────────────────────────┐
│  Acidni-LLC Organization                │
│  ┌─────────────────────────────────┐    │
│  │  Organization Secrets           │    │
│  │  • AZURE_CREDENTIALS            │    │
│  │  • ACR_USERNAME                 │    │
│  │  • ACR_PASSWORD                 │    │
│  │  • APIM_SUBSCRIPTION_KEY        │    │
│  │  • GH_PAT_TERPRINT_TESTS        │    │
│  │  • AZURE_ARTIFACTS_TOKEN        │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
         │         │         │
         ▼         ▼         ▼
    repo-1    repo-2    repo-3
    
✅ Solution: 1 organization × 8 secrets = 8 secrets total
```

---

## Organization Secrets to Create

### Required Secrets

| Secret Name | Description | How to Obtain |
|-------------|-------------|---------------|
| `ORG_AZURE_CREDENTIALS` | Azure Service Principal JSON | See [Creating Service Principal](#creating-service-principal) |
| `ORG_AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | `bb40fccf-9ffa-4bad-b9c0-ea40e326882c` |
| `ORG_AZURE_TENANT_ID` | Azure AD Tenant ID | `3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd` |
| `ORG_ACR_USERNAME` | Azure Container Registry username | `crterprint` |
| `ORG_ACR_PASSWORD` | Azure Container Registry password | From Key Vault or `az acr credential show` |
| `ORG_APIM_SUBSCRIPTION_KEY` | APIM gateway subscription key | From Key Vault `apim-subscription-key` |
| `ORG_GH_PAT_TERPRINT_TESTS` | PAT for triggering integration tests | GitHub Settings > Developer settings |
| `ORG_AZURE_ARTIFACTS_TOKEN` | Azure DevOps Artifacts PAT | Azure DevOps > Personal Access Tokens |

**Naming Convention:** Prefix with `ORG_` to distinguish from repo-level secrets.

### Optional Secrets (Service-Specific)

| Secret Name | Description | Used By |
|-------------|-------------|---------|
| `ORG_OPENAI_API_KEY` | Azure OpenAI API key | AI services |
| `ORG_COSMOS_CONNECTION_STRING` | Cosmos DB connection | Data services |
| `ORG_SQL_CONNECTION_STRING` | Azure SQL connection | Data services |

---

## Organization Variables to Create

GitHub Variables are **non-sensitive** configuration values that can be referenced in workflows.

### Required Variables

| Variable Name | Value | Description |
|---------------|-------|-------------|
| `ORG_ACR_LOGIN_SERVER` | `crterprint.azurecr.io` | Primary ACR |
| `ORG_APIM_BASE_URL` | `https://apim-terprint-dev.azure-api.net` | APIM gateway |
| `ORG_CONTAINER_ENV` | `kindmoss-c6723cbe.eastus2.azurecontainerapps.io` | Container Apps Environment |
| `ORG_RESOURCE_GROUP_PREFIX` | `rg-dev-terprint` | Default RG prefix |
| `ORG_PYTHON_VERSION` | `3.12` | Default Python version |
| `ORG_DOTNET_VERSION` | `8.0` | Default .NET version |

---

## Creating Service Principal

Create an organization-wide service principal with appropriate permissions:

```bash
# Create Service Principal for GitHub Actions (organization-wide)
az ad sp create-for-rbac \
  --name "sp-github-acidni-org" \
  --role contributor \
  --scopes \
    /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-shared \
    /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-ca \
    /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-terprint-apim-dev \
  --sdk-auth

# Output will be JSON - copy to ORG_AZURE_CREDENTIALS
```

### Assign Additional Permissions

```bash
# Get the Service Principal ID
SP_APPID=$(az ad sp list --display-name "sp-github-acidni-org" --query "[0].appId" -o tsv)

# Grant ACR Pull/Push
az role assignment create \
  --assignee $SP_APPID \
  --role AcrPush \
  --scope /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-health/providers/Microsoft.ContainerRegistry/registries/crterprint

# Grant Key Vault Secrets User
az role assignment create \
  --assignee $SP_APPID \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-shared/providers/Microsoft.KeyVault/vaults/kv-terprint-dev
```

---

## Setting Up Organization Secrets (GitHub UI)

1. **Navigate to Organization Settings**
   - Go to https://github.com/organizations/Acidni-LLC/settings/secrets/actions

2. **Add New Organization Secret**
   - Click **"New organization secret"**
   - Enter secret name (e.g., `ORG_AZURE_CREDENTIALS`)
   - Paste secret value
   - **Repository access**: Select **"All repositories"** or specific repos
   - Click **"Add secret"**

3. **Repeat for All Secrets** (from table above)

---

## Setting Up Organization Variables (GitHub UI)

1. **Navigate to Organization Variables**
   - Go to https://github.com/organizations/Acidni-LLC/settings/variables/actions

2. **Add New Organization Variable**
   - Click **"New organization variable"**
   - Enter variable name (e.g., `ORG_ACR_LOGIN_SERVER`)
   - Enter variable value (`crterprint.azurecr.io`)
   - **Repository access**: Select **"All repositories"**
   - Click **"Add variable"**

3. **Repeat for All Variables**

---

## Setting Up via GitHub CLI

```bash
# Authenticate to GitHub CLI
gh auth login

# Set organization secrets
gh secret set ORG_AZURE_CREDENTIALS --org Acidni-LLC --body "$(cat azure-credentials.json)" --visibility all
gh secret set ORG_ACR_USERNAME --org Acidni-LLC --body "crterprint" --visibility all
gh secret set ORG_ACR_PASSWORD --org Acidni-LLC --body "$(az acr credential show --name crterprint --query 'passwords[0].value' -o tsv)" --visibility all
gh secret set ORG_APIM_SUBSCRIPTION_KEY --org Acidni-LLC --body "$(az keyvault secret show --vault-name kv-terprint-dev --name apim-subscription-key --query value -o tsv)" --visibility all

# Set organization variables
gh variable set ORG_ACR_LOGIN_SERVER --org Acidni-LLC --body "crterprint.azurecr.io" --visibility all
gh variable set ORG_APIM_BASE_URL --org Acidni-LLC --body "https://apim-terprint-dev.azure-api.net" --visibility all
gh variable set ORG_PYTHON_VERSION --org Acidni-LLC --body "3.12" --visibility all
```

---

## Updated Reusable Workflow Pattern

The `terprint-config/.github/workflows/reusable-deploy.yml` now uses organization secrets:

```yaml
on:
  workflow_call:
    secrets:
      # Organization secrets are automatically inherited
      # No need to pass them explicitly when using 'secrets: inherit'
      
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.ORG_AZURE_CREDENTIALS }}  # From org
      
      - uses: docker/login-action@v3
        with:
          registry: ${{ vars.ORG_ACR_LOGIN_SERVER }}    # From org variable
          username: ${{ secrets.ORG_ACR_USERNAME }}     # From org secret
          password: ${{ secrets.ORG_ACR_PASSWORD }}     # From org secret
```

---

## Migration Steps for Existing Repos

### 1. Update Workflow to Use Reusable Workflow

**Before:**
```yaml
# .github/workflows/deploy.yml
jobs:
  build:
    steps:
      - uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}  # Repo-level
```

**After:**
```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    uses: Acidni-LLC/terprint-config/.github/workflows/reusable-deploy.yml@main
    with:
      app-name: 'ai-chat'
      environment: 'dev'
    secrets: inherit  # Inherits org secrets automatically
```

### 2. Remove Duplicate Repository Secrets

After verifying the workflow works with org secrets:

```bash
# List repo secrets (to verify what to delete)
gh secret list --repo Acidni-LLC/terprint-ai-chat

# Delete duplicate secrets (example - do for each repo)
gh secret delete AZURE_CREDENTIALS --repo Acidni-LLC/terprint-ai-chat
gh secret delete ACR_USERNAME --repo Acidni-LLC/terprint-ai-chat
gh secret delete ACR_PASSWORD --repo Acidni-LLC/terprint-ai-chat
```

### 3. Keep Repository-Specific Secrets

Some secrets are truly repo-specific (e.g., service principal for a specific service):

```yaml
# Still in repo secrets:
- REPO_SPECIFIC_API_KEY
- SERVICE_CLIENT_SECRET
```

---

## Verification Checklist

After migration, verify each repo:

- [ ] Workflow runs successfully
- [ ] Can build Docker image
- [ ] Can push to ACR
- [ ] Can deploy to Container Apps
- [ ] Health check passes
- [ ] Integration tests trigger
- [ ] No hardcoded secrets in code
- [ ] Repository secrets cleaned up

---

## Secret Rotation Process

### Before (50+ repos)
```bash
# ❌ Old way - update 50+ repos
for repo in repo1 repo2 repo3 ...; do
  gh secret set AZURE_CREDENTIALS --repo $repo --body "$(cat new-creds.json)"
done
```

### After (1 organization)
```bash
# ✅ New way - update once
gh secret set ORG_AZURE_CREDENTIALS --org Acidni-LLC --body "$(cat new-creds.json)" --visibility all
```

---

## Troubleshooting

### "Secret not found" Error

**Cause:** Org secret doesn't have access to the repository

**Solution:**
1. Go to org secret settings
2. Change "Repository access" to "All repositories" or add specific repo

### Workflow Still Uses Old Secret Name

**Cause:** Workflow references `secrets.AZURE_CREDENTIALS` instead of `secrets.ORG_AZURE_CREDENTIALS`

**Solution:** Update workflow to use new naming convention OR use `secrets: inherit` pattern

### "Unauthorized" When Pushing to ACR

**Cause:** Service principal doesn't have `AcrPush` role

**Solution:**
```bash
az role assignment create \
  --assignee $(az ad sp list --display-name "sp-github-acidni-org" --query "[0].appId" -o tsv) \
  --role AcrPush \
  --scope /subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-dev-terprint-health/providers/Microsoft.ContainerRegistry/registries/crterprint
```

---

## Security Best Practices

1. **Principle of Least Privilege**
   - Only grant org secrets to repos that need them
   - Use scoped service principals

2. **Secret Rotation**
   - Rotate `ORG_AZURE_CREDENTIALS` every 90 days
   - Rotate `ORG_ACR_PASSWORD` every 180 days
   - Rotate PATs annually

3. **Audit Access**
   - Review org secret access logs monthly
   - Monitor for unexpected workflow runs

4. **Never Log Secrets**
   ```yaml
   # ❌ WRONG
   - run: echo "Secret is ${{ secrets.ORG_AZURE_CREDENTIALS }}"
   
   # ✅ CORRECT
   - run: echo "Deploying with service principal..."
   ```

---

## Rollback Plan

If migration causes issues:

1. **Re-add repo-level secrets** temporarily
2. **Update workflow** to use `secrets.AZURE_CREDENTIALS` instead of `secrets.ORG_AZURE_CREDENTIALS`
3. **Investigate** and fix the root cause
4. **Re-attempt** migration

---

## Next Steps

1. **Create organization secrets** in GitHub (UI or CLI)
2. **Update `reusable-deploy.yml`** to reference org secrets
3. **Pilot migration** with 2-3 low-risk repos (e.g., `terprint-ai-lab`)
4. **Verify** all workflows pass
5. **Migrate all repos** systematically
6. **Clean up** duplicate repo secrets
7. **Document** in each repo's README

---

## Related Documentation

- [GitHub Organization Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets#creating-encrypted-secrets-for-an-organization)
- [Terprint CI/CD Instructions](../.github/instructions/terprint-cicd.instructions.md)
- [Azure Well-Architected Framework - Operational Excellence](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/)
- [Reusable Workflow Template](../.github/workflows/reusable-deploy.yml)

---

**Status:** Ready for implementation  
**Owner:** DevOps Team  
**Priority:** High (reduces operational overhead)
