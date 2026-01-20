---
description: 'Azure API Management (APIM) standards and patterns for Terprint services - routing, policies, caching, security, and service mesh'
applyTo: '**/apim/**,**/*policy*.xml,**/openapi*.json,**/openapi*.yaml,**/*client*.py,**/*api*.py,**/*service*.py,**/*client*.ts,**/*api*.ts,**/*service*.ts'
---

# Azure API Management (APIM) Instructions

## [!] CRITICAL DIRECTIVE: ALL TRAFFIC THROUGH APIM [!]

> **NO DIRECT SERVICE-TO-SERVICE CALLS ARE ALLOWED**

- ALL inter-service communication MUST route through APIM
- APIM is the single entry point for ALL Terprint APIs
- Backend services are NOT publicly accessible
- APIM handles: auth, rate limiting, caching, logging, transformation

## APIM Instance Details

| Property | Value |
|----------|-------|
| Instance Name | `apim-terprint-dev` |
| Resource Group | `rg-dev-terprint-shared` |
| Gateway URL | `https://apim-terprint-dev.azure-api.net` |
| Developer Portal | `https://apim-terprint-dev.developer.azure-api.net` |
| Management API | `https://apim-terprint-dev.management.azure-api.net` |
| SKU | Developer (upgrade to Standard for prod) |

## API Catalog

| API ID | Display Name | Path | Backend | Caching |
|--------|--------------|------|---------|---------|
| `terprint-communications` | Communications API | `/communications` | func-terprint-communications | 60s |
| `terprint-ai-chat-api` | AI Chat API | `/chat` | func-dev-terprint-ai-chat | 300s |
| `terprint-ai-recommender-api` | AI Recommender API | `/recommend` | func-terprint-ai-recommender | 600s |
| `terprint-data-api` | Data API | `/data` | func-terprint-data-api | 300s |
| `terprint-infographics` | Infographics API | `/infographics` | func-terprint-infographics | 86400s |
| `terprint-stock-api` | Stock API | `/stock` | terprint-menu-downloader | 3600s |
| `terprint-ai-lab` | AI Lab API | `/lab` | func-terprint-ai-lab | disabled |

## Calling Services Through APIM

### Base URL Pattern

```
https://apim-terprint-dev.azure-api.net/{api-path}/{endpoint}
```

### Example Calls

```powershell
# AI Chat - through APIM
$response = Invoke-RestMethod -Uri "https://apim-terprint-dev.azure-api.net/chat/api/chat" `
    -Method Post `
    -Headers @{ "Ocp-Apim-Subscription-Key" = $subscriptionKey } `
    -Body $body `
    -ContentType "application/json"

# Data API - through APIM  
$strains = Invoke-RestMethod -Uri "https://apim-terprint-dev.azure-api.net/data/api/strains" `
    -Headers @{ "Ocp-Apim-Subscription-Key" = $subscriptionKey }

# Stock Check - through APIM
$stock = Invoke-RestMethod -Uri "https://apim-terprint-dev.azure-api.net/stock/api/stock-check" `
    -Method Post `
    -Headers @{ "Ocp-Apim-Subscription-Key" = $subscriptionKey } `
    -Body '{"dispensary": "cookies"}' `
    -ContentType "application/json"
```

### Python SDK Pattern

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
        """Call AI Chat API through APIM."""
        response = requests.post(
            f"{self.base_url}/chat/api/chat",
            headers=self._get_headers(),
            json={"message": message, "session_id": session_id}
        )
        response.raise_for_status()
        return response.json()
    
    def get_recommendations(self, strain_id: str) -> dict:
        """Call AI Recommender API through APIM."""
        response = requests.get(
            f"{self.base_url}/recommend/api/recommendations/{strain_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()
    
    def get_strains(self, query: str = None) -> list:
        """Call Data API through APIM."""
        params = {"q": query} if query else {}
        response = requests.get(
            f"{self.base_url}/data/api/strains",
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()
```

## Authentication Methods

### 1. Subscription Key (Default)

```http
GET https://apim-terprint-dev.azure-api.net/data/api/strains
Ocp-Apim-Subscription-Key: {your-subscription-key}
```

### 2. OAuth 2.0 / Entra ID (Recommended for Production)

```http
GET https://apim-terprint-dev.azure-api.net/data/api/strains
Authorization: Bearer {access-token}
```

### 3. Client Certificate (For High-Security Endpoints)

Configured per-API in APIM policies.

## Internal Service API Keys

> **⚠️ CONFIDENTIAL** - Do not commit actual keys to git. Use Azure Key Vault in production.

These are the internal service-to-service API keys for backend services to call APIs through APIM.
Calls made with these keys are **NOT billed** to customers - they are identified by `svc-*` prefix.

### Backend Services (Reference Only - DO NOT CALL DIRECTLY)

> **All services are now Container Apps** (migrated from Azure Functions on 2026-01-06)

| API | Container App Name | Backend URL (FOR REFERENCE ONLY) |
|-----|-------------------|----------------------------------|
| Communications | `func-terprint-communications` | `https://func-terprint-communications.greensky-9390af85.eastus.azurecontainerapps.io/api` |
| AI Chat | `ca-terprint-ai-chat` | `https://ca-terprint-ai-chat.greensky-9390af85.eastus.azurecontainerapps.io/api` |
| AI Deals | `ca-terprint-ai-deals` | `https://ca-terprint-ai-deals.happyflower-d0e85283.eastus.azurecontainerapps.io/api` |
| AI Lab | `ca-terprint-ai-lab` | `https://ca-terprint-ai-lab.livelyfield-beaa429b.eastus.azurecontainerapps.io/api` |
| AI Recommender | `ca-terprint-ai-recommender` | `https://ca-terprint-ai-recommender.blacksky-230827a0.eastus2.azurecontainerapps.io/api` |
| Data API | `capp-terprint-data-api` | `https://capp-terprint-data-api.proudcoast-fb994cae.eastus.azurecontainerapps.io/api` |
| Menu Downloader | `ca-terprint-menudownloader` | `https://ca-terprint-menudownloader.blacksky-230827a0.eastus2.azurecontainerapps.io/api` |
| Stock API | (shares AI Deals backend) | `https://ca-terprint-ai-deals.happyflower-d0e85283.eastus.azurecontainerapps.io/api/stock` |
| Infographics | `func-terprint-infographics` | `https://func-terprint-infographics.azurewebsites.net/api` (still Function App) |

> **⚠️ SECURITY:**
> - All backends require `X-Backend-Api-Key` header (injected by APIM global policy)
> - **NEVER call these URLs directly** - Always use APIM gateway!
> - Backend API key stored in Key Vault: `kv-terprint-dev/backend-api-key`

### Internal Service Subscription Keys

| Service | Subscription ID | Environment Variable |
|---------|-----------------|----------------------|
| Communications | `svc-communications` | `APIM_SUBSCRIPTION_KEY` |
| Infographics | `svc-infographics` | `APIM_SUBSCRIPTION_KEY` |
| AI Chat | `svc-ai-chat` | `APIM_SUBSCRIPTION_KEY` |
| AI Recommender | `svc-ai-recommender` | `APIM_SUBSCRIPTION_KEY` |
| AI Lab | `svc-ai-lab` | `APIM_SUBSCRIPTION_KEY` |
| AI Deals | `svc-ai-deals` | `APIM_SUBSCRIPTION_KEY` |
| COA Extractor | `svc-coa-extractor` | `APIM_SUBSCRIPTION_KEY` |
| Stock API | `svc-stock-api` | `APIM_SUBSCRIPTION_KEY` |
| Metering | `svc-metering` | `APIM_SUBSCRIPTION_KEY` |

> **Keys are stored in Azure Key Vault** - Get from `kv-terprint` or `kv-terprint-prod`

### Getting Service Keys from Azure

```powershell
# Get a service subscription key (replace svc-infographics with your service)
az rest --method POST `
  --uri "https://management.azure.com/subscriptions/bb40fccf-9ffa-4bad-b9c0-ea40e326882c/resourceGroups/rg-terprint-apim-dev/providers/Microsoft.ApiManagement/service/apim-terprint-dev/subscriptions/svc-infographics/listSecrets?api-version=2023-05-01-preview" `
  --query primaryKey -o tsv
```

### Environment Variable Configuration

**For Azure Function Apps (via Azure CLI):**
```bash
az functionapp config appsettings set \
  --name func-terprint-infographics \
  --resource-group rg-terprint-dev \
  --settings APIM_GATEWAY_URL="https://apim-terprint-dev.azure-api.net" \
             APIM_SUBSCRIPTION_KEY="@Microsoft.KeyVault(SecretUri=https://kv-terprint.vault.azure.net/secrets/svc-infographics-key)" \
             DATA_API_BASE_URL="https://apim-terprint-dev.azure-api.net/data"
```

**For Local Development (`local.settings.json`):**
```json
{
  "Values": {
    "APIM_GATEWAY_URL": "https://apim-terprint-dev.azure-api.net",
    "APIM_SUBSCRIPTION_KEY": "<your-svc-key-from-keyvault>",
    "DATA_API_BASE_URL": "https://apim-terprint-dev.azure-api.net/data"
  }
}
```

### Metering Behavior

| Key Type | Prefix | Billed | Rate Limited |
|----------|--------|--------|--------------|
| Customer | (varies) | ✅ Yes | ✅ By tier |
| Internal Service | `svc-*` | ❌ No | ✅ Professional tier |

The metering service filters out calls from `svc-*` subscriptions so internal service-to-service calls don't generate customer bills.

## Products and Subscriptions

### Products

| Product | APIs Included | Rate Limit | Use Case |
|---------|---------------|------------|----------|
| `terprint-internal` | All APIs | Unlimited | Internal services |
| `terprint-web` | Data, Recommender, Infographics | 1000/min | Web application |
| `terprint-partner` | Data, Stock | 100/min | Partner integrations |
| `terprint-public` | Data (read-only) | 10/min | Public access |

### Getting a Subscription Key

```powershell
# List existing subscriptions
az apim subscription list `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --output table

# Create new subscription
az apim subscription create `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --subscription-id "my-app-subscription" `
    --display-name "My App Subscription" `
    --product-id terprint-internal `
    --output json

# Get subscription key
az apim subscription show `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --subscription-id "my-app-subscription" `
    --query "primaryKey" -o tsv
```

## APIM Policies

### Global Policy (All APIs)

```xml
<policies>
    <inbound>
        <!-- CORS for web clients -->
        <cors allow-credentials="true">
            <allowed-origins>
                <origin>https://terprint.com</origin>
                <origin>https://sales.terprint.com</origin>
                <origin>https://terprint.acidni.net</origin>
                <origin>http://localhost:3000</origin>
            </allowed-origins>
            <allowed-methods preflight-result-max-age="300">
                <method>GET</method>
                <method>POST</method>
                <method>PUT</method>
                <method>DELETE</method>
                <method>OPTIONS</method>
            </allowed-methods>
            <allowed-headers>
                <header>*</header>
            </allowed-headers>
        </cors>
        
        <!-- Rate limiting -->
        <rate-limit-by-key 
            calls="1000" 
            renewal-period="60" 
            counter-key="@(context.Subscription?.Key ?? context.Request.IpAddress)" />
        
        <!-- Request ID for tracing -->
        <set-header name="x-request-id" exists-action="skip">
            <value>@(Guid.NewGuid().ToString())</value>
        </set-header>
        
        <base />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <!-- Add response headers -->
        <set-header name="X-Powered-By" exists-action="delete" />
        <set-header name="X-Request-Id" exists-action="override">
            <value>@(context.RequestId.ToString())</value>
        </set-header>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

### Caching Policy Template

```xml
<policies>
    <inbound>
        <base />
        <!-- Check cache -->
        <cache-lookup vary-by-developer="false" 
                      vary-by-developer-groups="false" 
                      vary-by-query-parameter="*"
                      caching-type="internal">
            <vary-by-header>Accept</vary-by-header>
        </cache-lookup>
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <!-- Store in cache -->
        <cache-store duration="300" />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

### Response Transformation Policy

```xml
<outbound>
    <base />
    <!-- Wrap response in standard envelope -->
    <set-body>@{
        var response = context.Response.Body.As<JObject>();
        return new JObject(
            new JProperty("success", true),
            new JProperty("data", response),
            new JProperty("requestId", context.RequestId.ToString()),
            new JProperty("timestamp", DateTime.UtcNow.ToString("o"))
        ).ToString();
    }</set-body>
</outbound>
```

### Backend Circuit Breaker

```xml
<backend>
    <retry condition="@(context.Response.StatusCode >= 500)" 
           count="3" 
           interval="1" 
           delta="1" 
           max-interval="10" 
           first-fast-retry="true">
        <forward-request buffer-request-body="true" />
    </retry>
</backend>
```

### JWT Validation Policy

```xml
<inbound>
    <base />
    <validate-jwt header-name="Authorization" 
                  failed-validation-httpcode="401" 
                  failed-validation-error-message="Unauthorized">
        <openid-config url="https://login.microsoftonline.com/3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd/v2.0/.well-known/openid-configuration" />
        <audiences>
            <audience>api://apim-terprint-dev</audience>
        </audiences>
        <issuers>
            <issuer>https://sts.windows.net/3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd/</issuer>
        </issuers>
        <required-claims>
            <claim name="roles" match="any">
                <value>Terprint.Read</value>
                <value>Terprint.Write</value>
            </claim>
        </required-claims>
    </validate-jwt>
</inbound>
```

## Adding New APIs to APIM

### Step 1: Ensure OpenAPI Spec Exists

Every API must have `openapi.json` in repo root:

```json
{
  "openapi": "3.0.1",
  "info": {
    "title": "My Service API",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "https://func-my-service.azurewebsites.net/api"
    }
  ],
  "paths": {
    "/health": {
      "get": {
        "operationId": "health",
        "responses": {
          "200": {
            "description": "Service is healthy"
          }
        }
      }
    }
  }
}
```

### Step 2: Import API to APIM

```powershell
# Import from OpenAPI spec
az apim api import `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --api-id my-service-api `
    --path /myservice `
    --specification-format OpenApiJson `
    --specification-url "https://raw.githubusercontent.com/Acidni-LLC/my-service/main/openapi.json"

# Or from local file
az apim api import `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --api-id my-service-api `
    --path /myservice `
    --specification-format OpenApiJson `
    --specification-path ./openapi.json
```

### Step 3: Configure Backend

```powershell
# Set backend URL
az apim api update `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --api-id my-service-api `
    --service-url "https://func-my-service.azurewebsites.net/api"
```

### Step 4: Add to Product

```powershell
# Add API to internal product
az apim product api add `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --product-id terprint-internal `
    --api-id my-service-api
```

### Step 5: Apply Caching Policy

```powershell
# Set operation policy with caching
az apim api operation policy create `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --api-id my-service-api `
    --operation-id my-operation `
    --xml-policy "@./policies/caching-policy.xml"
```

## Monitoring and Diagnostics

### Enable Application Insights

```powershell
# Link App Insights to APIM
az apim update `
    --resource-group rg-dev-terprint-shared `
    --name apim-terprint-dev `
    --set properties.customProperties."Microsoft.WindowsAzure.ApiManagement.Gateway.Protocols.Server.Http2"="True"

# Create logger
az apim logger create `
    --resource-group rg-dev-terprint-shared `
    --service-name apim-terprint-dev `
    --logger-id appinsights-logger `
    --logger-type applicationInsights `
    --instrumentation-key "<APP_INSIGHTS_KEY>"
```

### Useful KQL Queries

```kql
// API request volume by operation
requests
| where cloud_RoleName == "apim-terprint-dev"
| summarize count() by operation_Name, bin(timestamp, 1h)
| order by timestamp desc

// Failed requests
requests
| where cloud_RoleName == "apim-terprint-dev"
| where success == false
| project timestamp, operation_Name, resultCode, duration
| order by timestamp desc

// Cache hit rate
customMetrics
| where name == "Cache Hit"
| summarize CacheHits = sum(value) by bin(timestamp, 1h)

// Latency by API
requests
| where cloud_RoleName == "apim-terprint-dev"
| summarize avg(duration), percentile(duration, 95), percentile(duration, 99) by operation_Name
```

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Unauthorized | Missing/invalid subscription key | Check `Ocp-Apim-Subscription-Key` header |
| 403 Forbidden | Subscription not authorized for product | Add API to subscription's product |
| 404 Not Found | Wrong path or API not imported | Check APIM path configuration |
| 429 Too Many Requests | Rate limit exceeded | Wait or request higher quota |
| 500 Backend Error | Backend service failing | Check backend service health |
| 504 Gateway Timeout | Backend too slow | Increase timeout or optimize backend |

### Debug Mode

Add trace to request:

```http
GET https://apim-terprint-dev.azure-api.net/data/api/strains
Ocp-Apim-Subscription-Key: {key}
Ocp-Apim-Trace: true
```

Response includes `Ocp-Apim-Trace-Location` header with debug trace URL.

### Test from Portal

1. Go to Azure Portal → APIM → APIs
2. Select API → Test tab
3. Select operation
4. Add headers/body
5. Click Send
6. View request/response trace

## Environment Variables

All services should use these environment variables:

```json
{
  "APIM_GATEWAY_URL": "https://apim-terprint-dev.azure-api.net",
  "APIM_SUBSCRIPTION_KEY": "@Microsoft.KeyVault(SecretUri=https://kv-terprint.vault.azure.net/secrets/apim-subscription-key/)",
  "APIM_MANAGEMENT_URL": "https://apim-terprint-dev.management.azure-api.net"
}
```

## Best Practices

1. **Always use APIM** - No direct backend calls
2. **Use subscription keys** - Don't expose backends publicly
3. **Enable caching** - Reduce backend load and latency
4. **Set rate limits** - Protect backends from overload
5. **Use OpenAPI specs** - Keep APIs documented and consistent
6. **Monitor everything** - App Insights integration required
7. **Version APIs** - Use path versioning `/v1/`, `/v2/`
8. **Handle errors gracefully** - Use APIM error policies
9. **Enable CORS** - Configure for web clients
10. **Use retry policies** - Handle transient failures

## Copy-Paste Ready: Service Client Code

### Python: APIM Client (Copy to your project)

```python
# apim_client.py - Copy this to your project
import os
import requests
from typing import Optional, Any
from dataclasses import dataclass

@dataclass
class APIMConfig:
    """APIM Configuration - loaded from environment."""
    gateway_url: str = "https://apim-terprint-dev.azure-api.net"
    subscription_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "APIMConfig":
        return cls(
            gateway_url=os.environ.get("APIM_GATEWAY_URL", "https://apim-terprint-dev.azure-api.net"),
            subscription_key=os.environ.get("APIM_SUBSCRIPTION_KEY")
        )

class TerprintAPIMClient:
    """
    Centralized client for calling Terprint services through APIM.
    
    Usage:
        client = TerprintAPIMClient()
        response = client.call_chat("What strain has limonene?")
        strains = client.get_strains(query="cookies")
    """
    
    # Service path mappings - NEVER call backends directly!
    SERVICES = {
        "communications": "/communications",
        "chat": "/chat",
        "recommend": "/recommend",
        "data": "/data",
        "infographics": "/infographics",
        "stock": "/stock",
    }
    
    def __init__(self, config: Optional[APIMConfig] = None):
        self.config = config or APIMConfig.from_env()
        self._session = requests.Session()
        
    def _get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.config.subscription_key:
            headers["Ocp-Apim-Subscription-Key"] = self.config.subscription_key
        return headers
    
    def _url(self, service: str, endpoint: str) -> str:
        """Build full APIM URL. NEVER call backend directly!"""
        path = self.SERVICES.get(service, f"/{service}")
        return f"{self.config.gateway_url}{path}{endpoint}"
    
    def call_chat(self, message: str, session_id: str = None) -> dict:
        """Call AI Chat service through APIM."""
        response = self._session.post(
            self._url("chat", "/api/chat"),
            headers=self._get_headers(),
            json={"message": message, "session_id": session_id}
        )
        response.raise_for_status()
        return response.json()
    
    def get_recommendations(self, strain_id: str) -> dict:
        """Call AI Recommender service through APIM."""
        response = self._session.get(
            self._url("recommend", f"/api/recommendations/{strain_id}"),
            headers=self._get_headers()
        )
        response.raise_for_status()
        return response.json()
    
    def get_strains(self, query: str = None) -> list:
        """Call Data API through APIM."""
        params = {"q": query} if query else {}
        response = self._session.get(
            self._url("data", "/api/strains"),
            headers=self._get_headers(),
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def send_email(self, to: str, subject: str, body: str) -> dict:
        """Call Communications service through APIM."""
        response = self._session.post(
            self._url("communications", "/api/send-email"),
            headers=self._get_headers(),
            json={"to": to, "subject": subject, "body": body}
        )
        response.raise_for_status()
        return response.json()
    
    def check_stock(self, dispensary: str, product_ids: list = None) -> dict:
        """Call Stock API through APIM."""
        response = self._session.post(
            self._url("stock", "/api/stock-check"),
            headers=self._get_headers(),
            json={"dispensary": dispensary, "product_ids": product_ids}
        )
        response.raise_for_status()
        return response.json()
    
    def generate_infographic(self, strain_id: str, template: str = "default") -> bytes:
        """Call Infographics service through APIM."""
        response = self._session.post(
            self._url("infographics", "/api/generate"),
            headers=self._get_headers(),
            json={"strain_id": strain_id, "template": template}
        )
        response.raise_for_status()
        return response.content
```

### TypeScript: APIM Client (Copy to your project)

```typescript
// apim-client.ts - Copy this to your project

interface APIMConfig {
  gatewayUrl: string;
  subscriptionKey?: string;
}

/**
 * Service path mappings - NEVER call backends directly!
 */
const SERVICES: Record<string, string> = {
  communications: "/communications",
  chat: "/chat",
  recommend: "/recommend",
  data: "/data",
  infographics: "/infographics",
  stock: "/stock",
};

export class TerprintAPIMClient {
  private config: APIMConfig;

  constructor(config?: Partial<APIMConfig>) {
    this.config = {
      gatewayUrl: config?.gatewayUrl || process.env.APIM_GATEWAY_URL || "https://apim-terprint-dev.azure-api.net",
      subscriptionKey: config?.subscriptionKey || process.env.APIM_SUBSCRIPTION_KEY,
    };
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (this.config.subscriptionKey) {
      headers["Ocp-Apim-Subscription-Key"] = this.config.subscriptionKey;
    }
    return headers;
  }

  private url(service: string, endpoint: string): string {
    const path = SERVICES[service] || `/${service}`;
    return `${this.config.gatewayUrl}${path}${endpoint}`;
  }

  async callChat(message: string, sessionId?: string): Promise<any> {
    const response = await fetch(this.url("chat", "/api/chat"), {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    if (!response.ok) throw new Error(`Chat API error: ${response.status}`);
    return response.json();
  }

  async getRecommendations(strainId: string): Promise<any> {
    const response = await fetch(this.url("recommend", `/api/recommendations/${strainId}`), {
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error(`Recommender API error: ${response.status}`);
    return response.json();
  }

  async getStrains(query?: string): Promise<any[]> {
    const url = new URL(this.url("data", "/api/strains"));
    if (query) url.searchParams.set("q", query);
    const response = await fetch(url.toString(), { headers: this.getHeaders() });
    if (!response.ok) throw new Error(`Data API error: ${response.status}`);
    return response.json();
  }

  async sendEmail(to: string, subject: string, body: string): Promise<any> {
    const response = await fetch(this.url("communications", "/api/send-email"), {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ to, subject, body }),
    });
    if (!response.ok) throw new Error(`Communications API error: ${response.status}`);
    return response.json();
  }

  async checkStock(dispensary: string, productIds?: string[]): Promise<any> {
    const response = await fetch(this.url("stock", "/api/stock-check"), {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify({ dispensary, product_ids: productIds }),
    });
    if (!response.ok) throw new Error(`Stock API error: ${response.status}`);
    return response.json();
  }
}

// Usage example:
// const client = new TerprintAPIMClient();
// const response = await client.callChat("What strains have myrcene?");
```

### C# / .NET: APIM Client (Copy to your project)

```csharp
// TerprintAPIMClient.cs - Copy this to your project
using System.Net.Http.Json;

public class TerprintAPIMClient : IDisposable
{
    private readonly HttpClient _client;
    private readonly string _gatewayUrl;
    
    private static readonly Dictionary<string, string> Services = new()
    {
        ["communications"] = "/communications",
        ["chat"] = "/chat",
        ["recommend"] = "/recommend",
        ["data"] = "/data",
        ["infographics"] = "/infographics",
        ["stock"] = "/stock",
    };
    
    public TerprintAPIMClient(string? gatewayUrl = null, string? subscriptionKey = null)
    {
        _gatewayUrl = gatewayUrl 
            ?? Environment.GetEnvironmentVariable("APIM_GATEWAY_URL") 
            ?? "https://apim-terprint-dev.azure-api.net";
            
        _client = new HttpClient();
        
        var key = subscriptionKey ?? Environment.GetEnvironmentVariable("APIM_SUBSCRIPTION_KEY");
        if (!string.IsNullOrEmpty(key))
        {
            _client.DefaultRequestHeaders.Add("Ocp-Apim-Subscription-Key", key);
        }
    }
    
    private string Url(string service, string endpoint)
    {
        var path = Services.GetValueOrDefault(service, $"/{service}");
        return $"{_gatewayUrl}{path}{endpoint}";
    }
    
    public async Task<T?> CallChatAsync<T>(string message, string? sessionId = null)
    {
        var response = await _client.PostAsJsonAsync(
            Url("chat", "/api/chat"),
            new { message, session_id = sessionId });
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>();
    }
    
    public async Task<T?> GetRecommendationsAsync<T>(string strainId)
    {
        var response = await _client.GetAsync(Url("recommend", $"/api/recommendations/{strainId}"));
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>();
    }
    
    public async Task<List<T>?> GetStrainsAsync<T>(string? query = null)
    {
        var url = string.IsNullOrEmpty(query) 
            ? Url("data", "/api/strains")
            : $"{Url("data", "/api/strains")}?q={Uri.EscapeDataString(query)}";
        var response = await _client.GetAsync(url);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<List<T>>();
    }
    
    public async Task<T?> SendEmailAsync<T>(string to, string subject, string body)
    {
        var response = await _client.PostAsJsonAsync(
            Url("communications", "/api/send-email"),
            new { to, subject, body });
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadFromJsonAsync<T>();
    }
    
    public void Dispose() => _client.Dispose();
}
```

## Quick Reference Commands

```powershell
# List all APIs
az apim api list -g rg-dev-terprint-shared -n apim-terprint-dev -o table

# List all products  
az apim product list -g rg-dev-terprint-shared -n apim-terprint-dev -o table

# List subscriptions
az apim subscription list -g rg-dev-terprint-shared -n apim-terprint-dev -o table

# Get API details
az apim api show -g rg-dev-terprint-shared -n apim-terprint-dev --api-id terprint-data-api

# Test API (get subscription key first)
$key = az apim subscription show -g rg-dev-terprint-shared -n apim-terprint-dev --subscription-id internal-key --query primaryKey -o tsv
Invoke-RestMethod -Uri "https://apim-terprint-dev.azure-api.net/data/api/health" -Headers @{"Ocp-Apim-Subscription-Key"=$key}
```
