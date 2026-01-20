---
description: 'Azure Functions development standards for Acidni LLC'
applyTo: '**/function.json, **/host.json, **/*_trigger.py, **/function_app.py'
---

# Azure Functions Development Instructions

Instructions for developing Azure Functions in Acidni LLC projects, focusing on serverless patterns and best practices.

## Project Context

- Runtime: Azure Functions v4
- Hosting: Consumption Plan (Linux)
- Languages: Python 3.12+ (primary), C# .NET 8 (secondary)
- Authentication: Entra ID (never API keys for app-to-app)

## Critical Rules

### Authentication Levels

```json
// ✅ CORRECT - Requires function key or bearer token
{
  "authLevel": "function",
  "type": "httpTrigger",
  "direction": "in",
  "name": "req",
  "methods": ["get", "post"]
}

// ❌ WRONG - No authentication (security risk)
{
  "authLevel": "anonymous",
  "type": "httpTrigger"
}
```

**Exception**: Health check endpoints (`/api/health`) may be anonymous for load balancer probes.

### App-to-App Authentication

Always use Entra ID Bearer tokens for service-to-service calls:

```python
from azure.identity import DefaultAzureCredential
import requests

def call_another_function(endpoint: str, scope: str) -> dict:
    """Call another Azure Function with Entra ID authentication."""
    credential = DefaultAzureCredential()
    token = credential.get_token(scope)
    
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()

# Usage
data = call_another_function(
    endpoint="https://func-terprint-communications.azurewebsites.net/api/send",
    scope="api://func-terprint-communications/.default"
)
```

### Token Validation

```python
import jwt
from functools import wraps

def require_auth(required_scopes: list[str] = None):
    """Decorator to validate Bearer tokens on incoming requests."""
    def decorator(func):
        @wraps(func)
        def wrapper(req: func.HttpRequest, *args, **kwargs):
            auth_header = req.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return func.HttpResponse(status_code=401)
            
            token = auth_header[7:]
            try:
                # Validate token (use proper key retrieval in production)
                payload = jwt.decode(
                    token,
                    options={"verify_signature": True},
                    audience=os.environ["AZURE_CLIENT_ID"]
                )
                
                if required_scopes:
                    token_scopes = payload.get("scp", "").split()
                    if not any(s in token_scopes for s in required_scopes):
                        return func.HttpResponse(status_code=403)
                        
            except jwt.InvalidTokenError:
                return func.HttpResponse(status_code=401)
            
            return func(req, *args, **kwargs)
        return wrapper
    return decorator
```

## [!] CRITICAL: Backend API Key Authentication [!]

> **All backends MUST validate the X-Backend-Api-Key header**

Since January 2026, APIM injects an `X-Backend-Api-Key` header on all requests to backend services.
This prevents direct access to backends, forcing all traffic through APIM.

### Choosing the Right Approach

| Platform | Approach | Notes |
|----------|----------|-------|
| **Azure Functions** | `@require_backend_api_key` decorator | Use on each HTTP-triggered function |
| **FastAPI (app-wide)** | `BackendApiKeyMiddleware` | Add once, protects all routes |
| **FastAPI (per-endpoint)** | `Depends(require_api_key())` | Fine-grained control, migration-friendly |

> ⚠️ **Common Mistake**: Do NOT use `@require_backend_api_key` decorator with FastAPI!
> The decorator expects `func.HttpRequest` (Azure Functions type). FastAPI uses different request types.

### Azure Functions (Decorator Pattern)

```python
import azure.functions as func
from terprint_config.middleware import require_backend_api_key

@app.route(route="chat", methods=["POST"])
@require_backend_api_key
async def chat(req: func.HttpRequest) -> func.HttpResponse:
    # Only runs if X-Backend-Api-Key is valid
    return func.HttpResponse('{"message": "OK"}', mimetype="application/json")

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    # NO decorator - health endpoints must be open for probes
    return func.HttpResponse('{"status": "healthy"}', mimetype="application/json")
```

### FastAPI / Container Apps (Middleware Pattern - RECOMMENDED)

```python
from fastapi import FastAPI
from terprint_config.middleware import BackendApiKeyMiddleware

app = FastAPI()

# Add middleware - automatically excludes /health, /api/health, /
app.add_middleware(BackendApiKeyMiddleware)

@app.get("/api/data")
async def get_data():
    # Protected by middleware
    return {"data": "value"}

@app.get("/api/health")
async def health():
    # NOT protected - excluded by default
    return {"status": "healthy"}
```

### FastAPI (Dependency Injection - Per-Endpoint Control)

Use when migrating from Azure Functions or need explicit per-endpoint control:

```python
from fastapi import FastAPI, Depends
from terprint_config.middleware import require_api_key

app = FastAPI()

@app.post("/api/chat")
async def chat(api_key: bool = Depends(require_api_key())):
    # Protected - requires valid X-Backend-Api-Key
    return {"message": "OK"}

@app.get("/api/health")
async def health():
    # NOT protected - no Depends()
    return {"status": "healthy"}
```

### Required Environment Variable

```json
// Container App or Function App settings
{
  "BACKEND_API_KEY": "@Microsoft.KeyVault(SecretUri=https://kv-terprint-dev.vault.azure.net/secrets/backend-api-key/)"
}
```

### Implementation Checklist

**For Azure Functions:**

1. Add `terprint-config>=4.8.0` to requirements.txt
2. Import `require_backend_api_key` from `terprint_config.middleware`
3. Apply decorator to all HTTP-triggered functions (except health)
4. Set `BACKEND_API_KEY` env var (Key Vault reference in Azure)

**For FastAPI/Container Apps:**

1. Add `terprint-config>=4.8.0` to pyproject.toml
2. Choose approach:
   - **Middleware** (recommended): `app.add_middleware(BackendApiKeyMiddleware)`
   - **Dependency**: `Depends(require_api_key())` on each endpoint
3. Set `BACKEND_API_KEY` env var (Key Vault reference in Azure)

> **Full Documentation**: See [docs/BACKEND_API_KEY_MIDDLEWARE.md](../../docs/BACKEND_API_KEY_MIDDLEWARE.md)

## Project Structure

```
function-app/
├── src/
│   ├── __init__.py
│   ├── function_app.py         # Main function app entry
│   ├── http_trigger/
│   │   ├── __init__.py
│   │   └── function.json
│   └── timer_trigger/
│       ├── __init__.py
│       └── function.json
├── tests/
├── host.json
├── local.settings.json         # Local development (gitignored)
├── requirements.txt
└── openapi.json               # API specification (required)
```

## Host Configuration

```json
// host.json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "maxTelemetryItemsPerSecond": 20,
        "excludedTypes": "Request"
      }
    },
    "logLevel": {
      "default": "Information",
      "Host.Results": "Error",
      "Function": "Information",
      "Host.Aggregator": "Trace"
    }
  },
  "extensions": {
    "http": {
      "routePrefix": "api",
      "maxConcurrentRequests": 100
    }
  },
  "functionTimeout": "00:10:00"
}
```

## [!] CRITICAL: ALL SECRETS MUST USE KEY VAULT [!]

> **NEVER hardcode secrets in local.settings.json or application settings**

### Key Vault References (Azure)

All production settings MUST use Key Vault references:

```json
// Application Settings in Azure Portal or Bicep
{
  "APIM_SUBSCRIPTION_KEY": "@Microsoft.KeyVault(SecretUri=https://kv-terprint.vault.azure.net/secrets/svc-myapp-key/)",
  "DATABASE_CONNECTION_STRING": "@Microsoft.KeyVault(SecretUri=https://kv-terprint.vault.azure.net/secrets/sql-connection-string/)",
  "OPENAI_API_KEY": "@Microsoft.KeyVault(SecretUri=https://kv-terprint.vault.azure.net/secrets/openai-api-key/)"
}
```

### Key Vaults

| Environment | Key Vault | Resource Group |
|-------------|-----------|----------------|
| Development | `kv-terprint` | `rg-dev-terprint-shared` |
| Production | `kv-terprint-prod` | `rg-prod-terprint-shared` |

### Required Secrets Per App

| Secret Name | Used By | Description |
|-------------|---------|-------------|
| `svc-{app}-key` | All apps | APIM subscription key for service |
| `sql-connection-string` | Data apps | Azure SQL connection |
| `openai-api-key` | AI apps | OpenAI API key |
| `acs-connection-string` | Communications | Azure Communication Services |
| `storage-connection-string` | Storage apps | Blob storage connection |
| `eventhouse-connection` | Analytics apps | Event House connection |

### Local Development Setup

For local development, create `local.settings.json` (gitignored) and retrieve secrets from Key Vault:

```powershell
# Get secrets from Key Vault for local development
$secrets = @{
    "APIM_SUBSCRIPTION_KEY" = az keyvault secret show --vault-name kv-terprint --name svc-ai-chat-key --query value -o tsv
    "OPENAI_API_KEY" = az keyvault secret show --vault-name kv-terprint --name openai-api-key --query value -o tsv
    "DATABASE_CONNECTION_STRING" = az keyvault secret show --vault-name kv-terprint --name sql-connection-string --query value -o tsv
}

# Display for copy-paste into local.settings.json
$secrets | ConvertTo-Json
```

### Managed Identity Setup

Function apps must have Managed Identity enabled and granted Key Vault access:

```powershell
# Enable system-assigned managed identity
az functionapp identity assign --name func-terprint-myapp --resource-group rg-dev-terprint-shared

# Grant Key Vault access
az keyvault set-policy --name kv-terprint \
    --object-id $(az functionapp identity show --name func-terprint-myapp --resource-group rg-dev-terprint-shared --query principalId -o tsv) \
    --secret-permissions get list
```

## Local Settings Template

```json
// local.settings.json (DO NOT COMMIT - in .gitignore)
// Get actual values from Key Vault using commands above
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AZURE_TENANT_ID": "3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd",
    "AZURE_CLIENT_ID": "<from-app-registration>",
    "APIM_GATEWAY_URL": "https://apim-terprint-dev.azure-api.net",
    "APIM_SUBSCRIPTION_KEY": "<from-keyvault: svc-{app}-key>",
    "DATABASE_CONNECTION_STRING": "<from-keyvault: sql-connection-string>"
  }
}
```

> **⚠️ NEVER commit local.settings.json** - It's in .gitignore for a reason!

## HTTP Trigger Patterns

### Standard Response Format

```python
import azure.functions as func
import json
from dataclasses import dataclass, asdict

@dataclass
class ApiResponse:
    success: bool
    data: dict | None = None
    error: str | None = None

def http_response(response: ApiResponse, status_code: int = 200) -> func.HttpResponse:
    """Create standardized HTTP response."""
    return func.HttpResponse(
        body=json.dumps(asdict(response)),
        status_code=status_code,
        mimetype="application/json"
    )

# Usage
def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        data = process_request(req)
        return http_response(ApiResponse(success=True, data=data))
    except ValidationError as e:
        return http_response(ApiResponse(success=False, error=str(e)), 400)
    except Exception as e:
        logger.exception("Unexpected error")
        return http_response(ApiResponse(success=False, error="Internal error"), 500)
```

### Timer Trigger Pattern

```python
import azure.functions as func
import logging

def main(timer: func.TimerRequest) -> None:
    """Run daily at 6 AM EST."""
    if timer.past_due:
        logging.warning("Timer is past due, running anyway")
    
    logging.info("Starting daily batch processing")
    try:
        process_daily_batch()
        logging.info("Daily batch processing completed successfully")
    except Exception as e:
        logging.exception(f"Daily batch processing failed: {e}")
        raise  # Re-raise to mark function as failed
```

```json
// function.json for timer
{
  "scriptFile": "__init__.py",
  "bindings": [
    {
      "name": "timer",
      "type": "timerTrigger",
      "direction": "in",
      "schedule": "0 0 11 * * *"  // 6 AM EST = 11 AM UTC
    }
  ]
}
```

## Local Testing Ports

Each function app has assigned ports for running multiple services locally:

| App | Default Port | Port Range |
|-----|--------------|------------|
| func-terprint-communications | 7071 | 7071-7075 |
| func-terprint-batchprocessor | 7076 | 7076-7080 |
| func-terprint-menudownloader | 7081 | 7081-7085 |
| func-terprint-ai-chat | 7086 | 7086-7090 |

```powershell
# Start with custom port and window title
$Host.UI.RawUI.WindowTitle = "🔔 Communications (7071)"
func host start --port 7071
```

## OpenAPI Specification

Every HTTP-triggered function app **MUST** have `openapi.json` in the repo root:

```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Terprint Communications API",
    "version": "1.0.0"
  },
  "servers": [
    {"url": "https://func-terprint-communications.azurewebsites.net"}
  ],
  "paths": {
    "/api/send-email": {
      "post": {
        "summary": "Send an email notification",
        "security": [{"bearerAuth": []}],
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {"$ref": "#/components/schemas/EmailRequest"}
            }
          }
        },
        "responses": {
          "200": {"description": "Email sent successfully"},
          "401": {"description": "Unauthorized"}
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "bearerAuth": {
        "type": "http",
        "scheme": "bearer"
      }
    }
  }
}
```

## Error Handling Best Practices

```python
class FunctionError(Exception):
    """Base class for function errors."""
    status_code: int = 500

class ValidationError(FunctionError):
    status_code = 400

class NotFoundError(FunctionError):
    status_code = 404

class UnauthorizedError(FunctionError):
    status_code = 401

def handle_errors(func):
    """Decorator for consistent error handling."""
    @wraps(func)
    def wrapper(req: func.HttpRequest, *args, **kwargs):
        try:
            return func(req, *args, **kwargs)
        except FunctionError as e:
            return http_response(
                ApiResponse(success=False, error=str(e)),
                e.status_code
            )
        except Exception as e:
            logging.exception("Unhandled exception")
            return http_response(
                ApiResponse(success=False, error="Internal server error"),
                500
            )
    return wrapper
```
