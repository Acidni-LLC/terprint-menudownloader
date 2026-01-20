---
description: 'Container Apps standards for Terprint microservices - deployment patterns, scaling, APIM integration, and consolidation'
applyTo: '**/Dockerfile,**/container-app*.bicep,**/*.containerapp.yml,**/docker-compose*.yml'
---

# Terprint Container Apps Instructions

## [!] CRITICAL: ALL SERVICES ARE CONTAINER APPS [!]

> **AZURE FUNCTIONS ARE LEGACY** - All new services MUST be Container Apps
> **CONSOLIDATE CAEs** - Use 3 environments: dev, staging, prod

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APIM Gateway                                  │
│               apim-terprint-dev.azure-api.net                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                Container App Environment                             │
│                   cae-terprint-dev (East US)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ AI Chat  │ │AI Recomm │ │ AI Deals │ │ Data API │ │  Comms   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │Menu DL   │ │  Batch   │ │Infograph │ │ Metering │                │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

## Container App Environment Consolidation

### Target Architecture (3 CAEs)

| Environment | Name | Location | Purpose |
|-------------|------|----------|---------|
| Development | `cae-terprint-dev` | East US | All dev apps |
| Staging | `cae-terprint-staging` | East US | Pre-prod testing |
| Production | `cae-terprint-prod` | East US | Production (zone-redundant) |

### CAE Naming Convention

```
cae-terprint-{environment}
```

- ✅ `cae-terprint-dev`
- ✅ `cae-terprint-staging`
- ✅ `cae-terprint-prod`
- ❌ `cae-terprint-ai-chat` (service-specific - DON'T DO THIS)
- ❌ `cae-ejhfbhp4ehvse` (random name - DON'T DO THIS)

## Container App Naming Convention

```
ca-terprint-{service-name}
```

| Service | Container App Name |
|---------|-------------------|
| AI Chat | `ca-terprint-ai-chat` |
| AI Recommender | `ca-terprint-ai-recommender` |
| AI Deals | `ca-terprint-ai-deals` |
| AI Lab | `ca-terprint-ai-lab` |
| Data API | `ca-terprint-data-api` |
| Communications | `ca-terprint-communications` |
| Menu Downloader | `ca-terprint-menudownloader` |
| Batch Processor | `ca-terprint-batchprocessor` |
| Infographics | `ca-terprint-infographics` |
| Metering | `ca-terprint-metering` |

## Dockerfile Standards

### Python Services (FastAPI/Functions)

```dockerfile
# Multi-stage build for Python services
FROM python:3.12-slim AS builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/packages -r requirements.txt

# Production image
FROM python:3.12-slim AS runtime
RUN groupadd -r terprint && useradd -r -g terprint terprint
WORKDIR /app

COPY --from=builder /app/packages /app/packages
ENV PYTHONPATH=/app/packages
COPY . .
RUN chown -R terprint:terprint /app
USER terprint

ENV PYTHONUNBUFFERED=1 PORT=80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
```

### .NET Services

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src
COPY ["*.csproj", "./"]
RUN dotnet restore
COPY . .
RUN dotnet publish -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
RUN groupadd -r terprint && useradd -r -g terprint terprint
COPY --from=build /app/publish .
RUN chown -R terprint:terprint /app
USER terprint

ENV ASPNETCORE_URLS=http://+:80
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/api/health || exit 1

ENTRYPOINT ["dotnet", "MyApp.dll"]
```

## Bicep Deployment

### Using the Container App Module

```bicep
// Deploy a Container App using the standard module
module aiChat 'br:acrterprintdev.azurecr.io/bicep/modules/container-app:v1' = {
  name: 'deploy-ai-chat'
  params: {
    location: location
    environment: 'dev'
    appName: 'ai-chat'
    containerImage: 'acrterprintdev.azurecr.io/terprint-ai-chat:latest'
    containerAppEnvironmentId: caeModule.outputs.environmentId
    appInsightsConnectionString: appInsights.properties.ConnectionString
    keyVaultName: 'kv-terprint-dev'
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: 0
    maxReplicas: 10
    externalIngress: false  // Only APIM can access
    targetPort: 80
    environmentVariables: [
      { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
      { name: 'COSMOS_DB_ENDPOINT', value: cosmosEndpoint }
    ]
    secrets: [
      { name: 'openai-key', keyVaultSecretName: 'openai-api-key', envVarName: 'AZURE_OPENAI_KEY' }
    ]
  }
}
```

### Full Deployment Example

```bicep
targetScope = 'subscription'

param location string = 'eastus'
param environment string = 'dev'

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-${environment}-terprint-shared'
  location: location
}

// Container App Environment (ONE per stage)
module cae 'modules/container-app-environment.bicep' = {
  scope: rg
  name: 'deploy-cae'
  params: {
    location: location
    environment: environment
    logAnalyticsWorkspaceId: logAnalytics.id
    zoneRedundant: environment == 'prod'
  }
}

// Deploy all services to the shared CAE
module aiChat 'modules/container-app.bicep' = {
  scope: rg
  name: 'deploy-ai-chat'
  params: {
    location: location
    environment: environment
    appName: 'ai-chat'
    containerImage: 'acrterprintdev.azurecr.io/terprint-ai-chat:${environment}-latest'
    containerAppEnvironmentId: cae.outputs.environmentId
    // ... other params
  }
}

module aiRecommender 'modules/container-app.bicep' = {
  scope: rg
  name: 'deploy-ai-recommender'
  params: {
    location: location
    environment: environment
    appName: 'ai-recommender'
    containerImage: 'acrterprintdev.azurecr.io/terprint-ai-recommender:${environment}-latest'
    containerAppEnvironmentId: cae.outputs.environmentId
    // ... other params
  }
}
```

## Scaling Configuration

### Default Scaling Rules

```bicep
scale: {
  minReplicas: 0      // Scale to zero when idle (cost savings)
  maxReplicas: 10     // Max instances
  rules: [
    {
      name: 'http-scale'
      http: {
        metadata: {
          concurrentRequests: '100'  // Scale up at 100 concurrent requests
        }
      }
    }
  ]
}
```

### Service-Specific Scaling

| Service | Min | Max | Scale Trigger |
|---------|-----|-----|---------------|
| AI Chat | 1 | 20 | 50 concurrent |
| AI Recommender | 0 | 10 | 100 concurrent |
| Data API | 1 | 15 | 100 concurrent |
| Batch Processor | 0 | 5 | Queue length |
| Menu Downloader | 0 | 3 | Timer/manual |
| Communications | 1 | 10 | 50 concurrent |

## Health Checks

### Required Endpoint

Every Container App MUST expose:

```
GET /api/health
```

Response (200 OK):
```json
{
  "status": "healthy",
  "service": "ai-chat",
  "version": "1.2.3",
  "timestamp": "2026-01-07T12:00:00Z"
}
```

### Probe Configuration

```bicep
probes: [
  {
    type: 'Liveness'
    httpGet: {
      path: '/api/health'
      port: 80
    }
    initialDelaySeconds: 10
    periodSeconds: 30
    failureThreshold: 3
  }
  {
    type: 'Readiness'
    httpGet: {
      path: '/api/health'
      port: 80
    }
    initialDelaySeconds: 5
    periodSeconds: 10
    failureThreshold: 3
  }
]
```

## APIM Integration

### Backend Configuration

All Container Apps are configured as APIM backends:

```xml
<set-backend-service base-url="https://ca-terprint-ai-chat.{cae-domain}.azurecontainerapps.io" />
```

### Ingress Configuration

```bicep
ingress: {
  external: false           // Internal only - APIM is the gateway
  targetPort: 80
  transport: 'auto'
  allowInsecure: false
  corsPolicy: {
    allowedOrigins: [
      'https://apim-terprint-dev.azure-api.net'
    ]
  }
}
```

## Migration from Azure Functions

### Migration Checklist

- [ ] Create Dockerfile using standard template
- [ ] Update `requirements.txt` to include `uvicorn`, `fastapi`
- [ ] Convert function triggers to FastAPI routes
- [ ] Add `/api/health` endpoint
- [ ] Test locally with `docker build` and `docker run`
- [ ] Push image to ACR
- [ ] Deploy Container App using Bicep module
- [ ] Update APIM backend URL
- [ ] Verify through APIM
- [ ] Delete legacy Function App

### Converting Function App to FastAPI

```python
# Before (Azure Functions)
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    name = req.params.get('name')
    return func.HttpResponse(f"Hello {name}")

# After (FastAPI for Container Apps)
from fastapi import FastAPI, Query

app = FastAPI()

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/hello")
async def hello(name: str = Query(None)):
    return {"message": f"Hello {name}"}
```

## Environment Variables

### Required for All Services

| Variable | Description |
|----------|-------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights telemetry |
| `ENVIRONMENT` | dev/staging/prod |
| `APP_NAME` | Service name |
| `APIM_GATEWAY_URL` | APIM base URL |

### Secrets (from Key Vault)

```bicep
secrets: [
  { name: 'apim-key', keyVaultSecretName: 'apim-subscription-key', envVarName: 'APIM_SUBSCRIPTION_KEY' }
  { name: 'sql-conn', keyVaultSecretName: 'sql-connection-string', envVarName: 'SQL_CONNECTION_STRING' }
]
```

## Dapr Integration (Optional)

For service-to-service communication without APIM:

```bicep
dapr: {
  enabled: true
  appId: 'ai-chat'
  appPort: 80
  appProtocol: 'http'
}
```

> **Note**: Only use Dapr for internal service mesh. External calls still go through APIM.

## Monitoring

### Application Insights

All services auto-report to shared App Insights:

- `appi-dev-terprint` (dev)
- `appi-staging-terprint` (staging)
- `appi-prod-terprint` (prod)

### Key Metrics

- Request rate
- Response time (P50, P95, P99)
- Error rate
- Container restarts
- CPU/Memory utilization

### Alerts

Configure alerts for:
- Error rate > 5%
- P95 latency > 2s
- Container restarts > 3 in 5 min
- Scale events
