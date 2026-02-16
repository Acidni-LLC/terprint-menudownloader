---
description: 'Terminal command patterns for Acidni LLC projects - Windows/PowerShell specifics, working commands, and known failure patterns'
applyTo: '**/*.ps1, **/*.sh, **/*.cmd, **/*.bat'
---

# Acidni Terminal Command Patterns

## [!] CRITICAL DIRECTIVES - READ FIRST [!]

> **THESE RULES ARE MANDATORY FOR ALL COPILOT INSTANCES ACROSS ALL REPOS**

### DIRECTIVE 1: NEVER MODIFY CODE OUTSIDE YOUR REPO

- **YOU ARE IN A SINGLE REPOSITORY** - Do NOT edit files in sibling repos
- **terprint-config owns shared resources** - Command registry, instructions, shared configs
- **YOUR REPO inherits these files** - They are READ-ONLY copies synced from terprint-config

### DIRECTIVE 2: HOW TO REQUEST CHANGES

If you need updates to shared resources (command registry, instructions, etc.):

1. **CREATE A WORK ITEM** in Azure DevOps (not a PR to terprint-config)
2. **Assign to Area Path**: `Terprint` (root area = terprint-config team)
3. **Tag with**: `shared-resources`, `terminal-patterns`, `command-registry`
4. **Describe**: What you need, why you need it, suggested solution

### DIRECTIVE 3: WHAT NOT TO DO

- [X] Do NOT edit `.github/commands/command-registry.json` in your repo
- [X] Do NOT edit `.github/instructions/*.instructions.md` in your repo  
- [X] Do NOT create duplicate command patterns in your repo
- [X] Do NOT assume your local copy is authoritative

### DIRECTIVE 4: SYNC PROCESS

The terprint-config team periodically syncs updates to all repos:
```powershell
# This runs FROM terprint-config, not from your repo
.\sync-command-registry.ps1
```

Your repo receives updates - it does not send them.

### DIRECTIVE 5: ALL APPS MUST BE CONTAINER APPS

- **ALL Terprint services MUST be containerized** (Docker)
- **Every repo MUST have a Dockerfile** in the root or appropriate location
- **Use multi-stage builds** for optimal image size
- **Base images**: Use official Microsoft images for .NET, Python
- **Health checks**: All containers MUST expose `/api/health` endpoint
- **See**: `.github/instructions/containerization-docker-best-practices.instructions.md`

**Required Files:**
```
your-repo/
  Dockerfile                    # Required
  .dockerignore                 # Required
  docker-compose.yml            # Optional for local dev
```

**Exception Process**: If your app cannot be containerized, create a work item with justification.

### DIRECTIVE 6: ALL APPS MUST USE CACHING

- **ALL apps MUST implement caching by default**
- **Cache layer**: Azure Cache for Redis (shared instance) or in-memory for local
- **Cache-aside pattern**: Check cache → miss → fetch → store → return
- **Default TTL**: 5 minutes (configurable per endpoint)
- **Cache keys**: Use consistent naming: `{service}:{entity}:{id}`

**Central Config Controls Caching:**
```json
// terprint-config/shared/cache-config.json
{
  "defaults": {
    "enabled": true,
    "ttlSeconds": 300,
    "provider": "redis"
  },
  "overrides": {
    "func-terprint-menudownloader": {
      "enabled": true,
      "ttlSeconds": 3600
    },
    "func-terprint-ai-lab": {
      "enabled": false,
      "reason": "Experimental - real-time data required"
    }
  }
}
```

**To Disable Caching**: Request via work item → terprint-config team adds override.

**Cache Implementation Pattern (Python):**
```python
from terprint_config.cache import get_cached, set_cached, cache_config

async def get_data(key: str):
    # Check if caching enabled for this service
    if cache_config.enabled:
        cached = await get_cached(f"myservice:{key}")
        if cached:
            return cached
    
    # Fetch fresh data
    data = await fetch_from_source(key)
    
    # Store in cache
    if cache_config.enabled:
        await set_cached(f"myservice:{key}", data, ttl=cache_config.ttl)
    
    return data
```

### DIRECTIVE 7: ALL SERVICE CALLS MUST GO THROUGH APIM

- **NO direct service-to-service calls** - ALL API calls route through APIM
- **APIM Gateway**: `https://apim-terprint-dev.azure-api.net`
- **Benefits**: Central auth, rate limiting, caching, monitoring, circuit breaking
- **Authentication**: Use subscription keys or OAuth tokens

**APIM API Paths (use these, not direct URLs):**
| Service | Direct URL (FORBIDDEN) | APIM Path (USE THIS) |
|---------|------------------------|----------------------|
| Communications | func-terprint-communications.azurewebsites.net | /communications |
| AI Chat | func-dev-terprint-ai-chat.azurewebsites.net | /chat |
| AI Recommender | func-terprint-ai-recommender.azurewebsites.net | /recommend |
| Data API | func-terprint-data-api.azurewebsites.net | /data |
| Stock API | terprint-menu-downloader.azurewebsites.net | /stock |
| Infographics | func-terprint-infographics.azurewebsites.net | /infographics |

**Python Pattern:**
```python
from terprint_config.apim import TerprintAPIClient

# Use APIM client - handles auth, retries, caching
client = TerprintAPIClient()
response = await client.call("communications", "/send-email", method="POST", data=payload)
```

**Exception**: Health checks from Azure Monitor may bypass APIM. Document all exceptions.

See: `.github/instructions/azure-apim.instructions.md` for comprehensive APIM guidance.

### DIRECTIVE 8: USE ASSIGNED PORTS FOR LOCAL DEVELOPMENT

> **DO NOT USE RANDOM PORTS - EACH APP HAS ASSIGNED PORTS**

Every Terprint service has pre-assigned ports to avoid conflicts when running multiple services locally.

**Port Assignment Table (AUTHORITATIVE):**

| App | Repo Name | Default Port | Port Range | Window Title |
|-----|-----------|--------------|------------|--------------|
| Communications | `func-terprint-communications` | **7071** | 7071-7075 | 🔔 Communications |
| Batch Creator | `terprint-batches` | **7076** | 7076-7080 | 📦 Batch Creator |
| COA Processor | `terprint-batch-processor` | **7081** | 7081-7085 | 🔧 COA Processor |
| Menu Downloader | `func-terprint-menudownloader` | **7086** | 7086-7090 | 📥 Menu Downloader |
| AI Chat | `func-terprint-ai-chat` | **7086** | 7086-7090 | 💬 AI Chat |
| AI Recommender | `func-terprint-ai-recommender` | **7091** | 7091-7095 | 🎯 AI Recommender |
| AI Deals | `func-terprint-ai-deals` | **7096** | 7096-7100 | 💰 AI Deals |
| AI Health | `func-terprint-ai-health` | **7101** | 7101-7105 | 🏥 AI Health |
| Marketplace Webhook | `acidni-publisher-portal-webhook` | **7106** | 7106-7110 | 🏪 Marketplace |
| Infographics | `func-terprint-infographics` | **7111** | 7111-7115 | 🎨 Infographics |
| Metering | `func-terprint-metering` | **7116** | 7116-7120 | 📊 Metering |
| Data API | `func-terprint-data-api` | **7121** | 7121-7125 | 📡 Data API |

**Why Port Ranges?**
- Each app gets 5 ports (e.g., 7071-7075) for debugging scenarios
- Use the **default port** for normal development
- Use alternate ports if you need multiple instances

**Starting an App Locally:**
```powershell
# ALWAYS set window title + use assigned port
$Host.UI.RawUI.WindowTitle = "🔔 Communications (7071)"
func host start --port 7071

# AI Chat on its assigned port
$Host.UI.RawUI.WindowTitle = "💬 AI Chat (7086)"
func host start --port 7086
```

**Local URLs for Testing:**
```
http://localhost:7071/api/...   # Communications
http://localhost:7076/api/...   # Batch Creator
http://localhost:7081/api/...   # COA Processor
http://localhost:7086/api/...   # Menu Downloader
http://localhost:7091/api/...   # AI Chat
http://localhost:7091/api/...   # AI Recommender
http://localhost:7096/api/...   # AI Deals
http://localhost:7101/api/...   # AI Health
http://localhost:7106/api/...   # Marketplace Webhook
http://localhost:7111/api/...   # Infographics
http://localhost:7116/api/...   # Metering
http://localhost:7121/api/...   # Data API
```

---

## TERMINAL ORCHESTRATOR & WINDOW TITLES

To avoid terminals fighting each other and to maximize local performance, use the **Terprint Terminal Orchestrator** instead of starting 8 random `func host start` sessions by hand.

### Terminal Orchestrator Design

- **Config**: `terprint-config/.github/commands/terminal-orchestrator.json` (profiles, ports, groups)
- **Script**: `terprint-config/.github/commands/Start-TerprintTerminals.ps1`
- **Profiles**:
  - `minimal`: `communications`, `ai-chat`
  - `ai-development`: `communications`, `ai-chat`, `ai-recommender`, `ai-deals`
  - `data-development`: `communications`, `batch-processor`, `menudownloader`, `data-api`
  - `full`: all 8 core services
- **Groups** (ordered startup):
  - `core-services` → `ai-services` → `data-services`
- **Behavior**:
  - Starts each service in its **own PowerShell window**
  - Sets a clear **window title** per app (see below)
  - Waits on health checks when needed to avoid race conditions

### REQUIRED: Window Title Per App

Every local service terminal MUST include the app name and port in the window title so engineers can see at a glance what is running.

**Standard format**: `AppName (Port)`

Examples (what the orchestrator already does):

```powershell
$Host.UI.RawUI.WindowTitle = "Communications (7071)"    # func-terprint-communications
$Host.UI.RawUI.WindowTitle = "Batch Creator (7076)"      # terprint-batches
$Host.UI.RawUI.WindowTitle = "COA Processor (7081)"      # terprint-batch-processor
$Host.UI.RawUI.WindowTitle = "Menu Downloader (7086)"    # terprint-menudownloader
$Host.UI.RawUI.WindowTitle = "Infographics (7111)"     # terprint-infographics
$Host.UI.RawUI.WindowTitle = "Data API (7121)"         # terprint-data
```

> If you start a function app manually, set the window title **before** running `func host start`.

### Recommended Commands

From `terprint-config` root:

```powershell
# Minimal profile (fastest for day-to-day AI work)
./.github/commands/Start-TerprintTerminals.ps1 -Action start -Profile minimal

# AI development profile
./.github/commands/Start-TerprintTerminals.ps1 -Action start -Profile ai-development

# Data development profile
./.github/commands/Start-TerprintTerminals.ps1 -Action start -Profile data-development

# Status and health
./.github/commands/Start-TerprintTerminals.ps1 -Action status
./.github/commands/Start-TerprintTerminals.ps1 -Action health
```

These commands are also exposed in VS Code as tasks ("Terprint: Start Minimal Profile", etc.).

---

## CENTRAL NAVIGATION - WHERE EVERYTHING LIVES

> **terprint-config is the single source of truth for all shared resources**

| What You Need | Where It Lives | How to Access |
|---------------|----------------|---------------|
| Working Commands | `.github/commands/command-registry.json` | Categories: azure, azure-devops, azure-apim, azure-cache, dotnet, python, git, docker, http |
| Failure Patterns | `.github/commands/command-registry.json` | Section: `failurePatterns` - what NOT to do |
| Terminal Patterns | `.github/instructions/acidni-terminal-patterns.instructions.md` | This file - platform-specific guidance |
| **APIM Instructions** | `.github/instructions/azure-apim.instructions.md` | **Comprehensive APIM guidance, policies, SDK patterns** |
| Master Instructions | `shared/acidni-copilot-instructions.md` | Company-wide standards (inherited by all) |
| Project Instructions | `.github/copilot-instructions.md` | Terprint-specific (extends master) |
| Azure Resources | `.github/copilot-instructions.md` | Section: AZURE RESOURCES QUICK REFERENCE |
| Port Assignments | `.github/commands/command-registry.json` | azure-functions category |
| App Registrations | `.github/copilot-instructions.md` | Section: App-to-App Authentication |
| DevOps Auth | `.github/commands/command-registry.json` | azure-devops category (SP login sequence) |
| Sync Targets | `.github/commands/sync-targets.json` | All 23 terprint projects |
| **Cache Config** | `shared/cache-config.json` | Per-service cache settings, TTL, enable/disable |
| **Container Standards** | `.github/instructions/containerization-docker-best-practices.instructions.md` | Dockerfile patterns, multi-stage builds |

### Command Registry Location

**Authoritative Source**: `terprint-config/.github/commands/command-registry.json`

```
terprint-config/
  .github/
    commands/
      command-registry.json      <-- THE source of truth
      command-registry.schema.json
      sync-targets.json
    instructions/
      acidni-terminal-patterns.instructions.md  <-- This file
```

**Your repo has a COPY at**: `your-repo/.github/commands/command-registry.json`
- This copy is synced from terprint-config
- Do NOT edit your local copy
- Changes go through work items to terprint-config team

---

## WORK ITEM WORKFLOW

### When to Create a Work Item

Create a work item when you need:
- New commands added to the registry
- Failure patterns documented
- Instruction updates
- Cross-repo configuration changes

### How to Create the Work Item

**Azure DevOps URL**: https://dev.azure.com/Acidni/Terprint

**Required Fields**:
| Field | Value |
|-------|-------|
| Type | Task |
| Title | `[shared-resources] Brief description of need` |
| Area Path | `Terprint` (root = terprint-config team) |
| Tags | `shared-resources`, plus: `command-registry`, `terminal-patterns`, `instructions` |
| Description | What you need, why, and suggested implementation |

**Example Work Item**:
```
Title: [shared-resources] Add npm cache commands to registry
Area: Terprint
Tags: shared-resources, command-registry
Description:
  Need: npm ci with cache flag for faster CI builds
  Why: Our builds take 3+ minutes, cache could reduce to <1 minute
  Suggested command: npm ci --cache .npm --prefer-offline
  Category: nodejs
```

### What Happens Next

1. terprint-config team reviews the work item
2. If approved, they update the authoritative source
3. Next sync distributes changes to all repos
4. Work item closed with link to the sync commit

---

## PowerShell Command Patterns (Windows)

### CRITICAL: VS Code Terminal Limitations

VS Code's integrated terminal has specific behaviors that differ from standalone PowerShell:

1. **Command Chaining**: Use `;` not `&&` (PowerShell syntax)
2. **Long Commands**: May timeout - break into separate executions
3. **Output Buffering**: Large outputs get truncated

### Working Patterns

**Sequential Commands** (dependencies):
```powershell
# CORRECT - PowerShell semicolon chaining
cd project-folder; dotnet build

# WRONG - Bash-style (fails in PowerShell)
cd project-folder && dotnet build
```

**Azure CLI Commands**:
```powershell
# CORRECT - Explicit output format
az account show --output json

# Listing with specific properties
az functionapp list --query "[].{name:name, state:state}" --output table
```

**dotnet Commands**:
```powershell
# Build with full paths for error navigation
dotnet build /property:GenerateFullPaths=true

# Test with specific filter
dotnet test --filter "FullyQualifiedName~UnitTests"
```

### HTTP Requests

**Invoke-RestMethod** (preferred for JSON APIs):
```powershell
# GET request
Invoke-RestMethod -Uri "https://api.example.com/data" -Method Get

# POST with body
$body = @{ key = "value" } | ConvertTo-Json
Invoke-RestMethod -Uri "https://api.example.com/data" -Method Post -Body $body -ContentType "application/json"

# With authentication header
$headers = @{ "Authorization" = "Bearer $token" }
Invoke-RestMethod -Uri "https://api.example.com/data" -Headers $headers
```

**Invoke-WebRequest** (when you need response details):
```powershell
# When you need status code, headers, etc.
$response = Invoke-WebRequest -Uri "https://api.example.com/data"
$response.StatusCode
$response.Headers
```

### Output Buffering Considerations

Large command outputs will be truncated. Strategies:

```powershell
# Redirect to file for large outputs
Get-ChildItem -Recurse | Out-File results.txt

# Filter early to reduce output
Get-Process | Where-Object { $_.CPU -gt 100 } | Select-Object Name, CPU

# Use pagination for exploration
Get-Help Get-Process -Full | more
```

---

## Azure Functions Local Testing

### Port Assignments

> **See DIRECTIVE 8 above for the authoritative port assignment table.**

Quick reference (default ports only):

| App | Port | Local URL |
|-----|------|-----------|
| Communications | 7071 | http://localhost:7071/api/ |
| Batch Creator | 7076 | http://localhost:7076/api/ |
| COA Processor | 7081 | http://localhost:7081/api/ |
| Menu Downloader | 7086 | http://localhost:7086/api/ |
| AI Chat | 7086 | http://localhost:7086/api/ |
| AI Recommender | 7091 | http://localhost:7091/api/ |
| AI Deals | 7096 | http://localhost:7096/api/ |
| AI Health | 7101 | http://localhost:7101/api/ |
| Marketplace Webhook | 7106 | http://localhost:7106/api/ |
| Infographics | 7111 | http://localhost:7111/api/ |
| Metering | 7116 | http://localhost:7116/api/ |
| Data API | 7121 | http://localhost:7121/api/ |

### Starting Functions Locally

```powershell
# With window title for identification
$Host.UI.RawUI.WindowTitle = "Communications (7071)"
func host start --port 7071
```

---

## Git Operations

### Standard Workflow

```powershell
# Check status first
git status

# Stage specific files (not git add .)
git add path/to/specific/file.py

# Commit with conventional format
git commit -m "feat(component): brief description"

# Push to remote
git push origin main
```

### Conventional Commit Types

| Type | Use For |
|------|---------|
| feat | New features |
| fix | Bug fixes |
| docs | Documentation only |
| chore | Maintenance, deps |
| test | Test additions |
| refactor | Code restructuring |

---

## Python Environment

### CRITICAL: Use pymssql NOT pyodbc

Azure Functions Consumption Plan runs on Linux without ODBC drivers:

```python
# CORRECT
import pymssql
cursor.execute("SELECT * FROM Users WHERE Id = %s", (user_id,))

# WRONG - will fail in Azure
import pyodbc
cursor.execute("SELECT * FROM Users WHERE Id = ?", (user_id,))
```

### Virtual Environment Setup

```powershell
# Create venv
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

---

## Azure CLI Patterns

### Authentication

```powershell
# Interactive login
az login

# With tenant (for multi-tenant)
az login --tenant 3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd

# Set subscription
az account set --subscription bb40fccf-9ffa-4bad-b9c0-ea40e326882c
```

### Resource Queries

```powershell
# List with JMESPath query
az functionapp list --query "[].{name:name, state:state}" --output table

# Get specific resource
az functionapp show --name func-terprint-communications --resource-group rg-dev-terprint-shared
```

---

## Azure DevOps Authentication (Service Principal)

### CRITICAL: Use Service Principal, NOT PAT

Personal Access Tokens (PAT) should not be used for automation. Use service principal authentication:

```powershell
# Step 1: Login to Azure with service principal
az login --service-principal `
    --username $env:AZURE_CLIENT_ID `
    --password $env:AZURE_CLIENT_SECRET `
    --tenant 3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd

# Step 2: Get token for Azure DevOps
$token = az account get-access-token `
    --resource 499b84ac-1321-427f-aa17-267ca6975798 `
    --query accessToken -o tsv

# Step 3: Configure Azure DevOps CLI
$env:AZURE_DEVOPS_EXT_PAT = $token
az devops configure --defaults organization=https://dev.azure.com/Acidni project=Terprint

# Step 4: Use DevOps commands
az boards work-item show --id 123
```

**Note**: Resource ID `499b84ac-1321-427f-aa17-267ca6975798` is the Azure DevOps resource.

---

## Known Failure Patterns

> **Reference the command registry for the complete list**: `.github/commands/command-registry.json`

### PowerShell Syntax Errors

| Pattern | Why It Fails | Fix |
|---------|--------------|-----|
| `&&` chaining | Not PowerShell syntax | Use `;` or separate commands |
| Inline `if` in hashtable | PS syntax error | Use ternary or pre-compute |
| `$variable` in double quotes without escape | Variable expansion | Use single quotes or backtick |

### VS Code Terminal Issues

| Pattern | Why It Fails | Fix |
|---------|--------------|-----|
| Long-running commands | Terminal timeout | Use `isBackground: true` or tasks |
| Large output | Buffer truncation | Redirect to file |
| Multiple chained commands | Timeout on sequence | Run separately |

### Azure Functions Issues

| Pattern | Why It Fails | Fix |
|---------|--------------|-----|
| `pyodbc` on Linux | No ODBC drivers | Use `pymssql` |
| Port conflicts | Multiple funcs on same port | Use assigned port ranges |
| Anonymous auth | Security violation | Use `AuthorizationLevel.Function` |

### Performance Patterns

| Symptom | Cause | Solution |
|---------|-------|----------|
| Command timeout | Too many ops chained | Break into separate commands |
| Slow response | Missing `--output` format | Add `--output json` or `table` |
| Memory issues | Large JSON parsing | Stream or paginate |

---

## Quick Reference Card

### Most Common Commands

```powershell
# Build .NET project
dotnet build /property:GenerateFullPaths=true

# Run Azure Function locally
func host start --port <assigned-port>

# Run Python tests
pytest tests/ -v

# Azure login
az login --tenant 3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd

# Git commit
git commit -m "feat(component): description"
```

### Emergency Contacts

| Resource | Location |
|----------|----------|
| Command Registry | terprint-config/.github/commands/command-registry.json |
| Master Instructions | terprint-config/shared/acidni-copilot-instructions.md |
| Azure DevOps | https://dev.azure.com/Acidni/Terprint |
| Create Work Item | Area Path: Terprint, Tag: shared-resources |
