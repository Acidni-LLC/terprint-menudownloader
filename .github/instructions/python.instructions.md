---
description: 'Python 3.12+ coding standards for Acidni LLC projects with Azure expertise'
applyTo: '**/*.py'
---

# Python Development Instructions for Azure

Instructions for Python development in Acidni LLC projects, targeting Python 3.12+ on Azure Functions, Container Apps, and Azure services.

## Project Context

- Target runtime: Python 3.12+
- Primary platforms: Azure Functions (Consumption Plan - Linux), Azure Container Apps
- Package management: pip with `requirements.txt` or `pyproject.toml`
- Testing: pytest
- Cloud platform: Microsoft Azure with full SDK integration
- Authentication: Azure Entra ID with managed identities

## Critical Azure Rules

### Database Drivers (Azure Functions Linux)

```python
# ✅ CORRECT - pymssql works on Azure Functions (Linux)
import pymssql
from azure.identity import DefaultAzureCredential

# With managed identity (preferred)
credential = DefaultAzureCredential()
token = credential.get_token("https://database.windows.net/.default")
conn = pymssql.connect(
    server=f"{server}.database.windows.net",
    database=database,
    user=managed_identity_client_id,
    password=token.token,
    port=1433
)
cursor = conn.cursor()
cursor.execute("SELECT * FROM Users WHERE Id = %s", (user_id,))

# With connection string (fallback)
conn = pymssql.connect(
    server=server,
    user=user, 
    password=password,
    database=database
)

# ❌ WRONG - pyodbc requires ODBC drivers (not available on Consumption Plan)
import pyodbc
conn = pyodbc.connect(connection_string)
cursor.execute("SELECT * FROM Users WHERE Id = ?", (user_id,))
```

### Azure SDK Authentication Patterns

```python
# ✅ CORRECT - Use DefaultAzureCredential for all Azure services
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.keyvault.secrets import SecretClient

# This handles managed identity, Azure CLI, environment variables, etc.
credential = DefaultAzureCredential()

# Blob Storage
blob_client = BlobServiceClient(
    account_url="https://storage.blob.core.windows.net",
    credential=credential
)

# Key Vault
vault_client = SecretClient(
    vault_url="https://vault.vault.azure.net",
    credential=credential
)

# ❌ WRONG - Hardcoded connection strings or keys
blob_client = BlobServiceClient.from_connection_string("DefaultEndpointsProtocol=https;...")
```

### Async Azure Operations

```python
# ✅ CORRECT - Async Azure SDK usage
import asyncio
from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential

async def upload_to_blob(data: bytes, container: str, blob_name: str) -> None:
    """Upload data to Azure Blob Storage asynchronously."""
    credential = DefaultAzureCredential()
    
    async with BlobServiceClient(
        account_url="https://storage.blob.core.windows.net",
        credential=credential
    ) as blob_service:
        blob_client = blob_service.get_blob_client(
            container=container, 
            blob=blob_name
        )
        await blob_client.upload_blob(data, overwrite=True)

# Use in Azure Functions
async def main(req: func.HttpRequest) -> func.HttpResponse:
    await upload_to_blob(b"data", "container", "file.json")
    return func.HttpResponse("Uploaded")
```

### Placeholder Syntax

| Driver | Placeholder | Example |
|--------|-------------|---------|
| pymssql | `%s` | `cursor.execute("WHERE id = %s", (id,))` |
| pyodbc | `?` | `cursor.execute("WHERE id = ?", (id,))` |

Always use `%s` for parameterized queries with pymssql.

## Type Hints

Use type hints for all function signatures:

```python
# ✅ Good - Clear type annotations
def process_batch(batch_id: str, options: dict[str, Any] | None = None) -> BatchResult:
    """Process a data batch."""
    pass

# ❌ Avoid - No type information
def process_batch(batch_id, options=None):
    pass
```

## Async/Await Patterns

For Azure Functions, prefer async when making I/O calls:

```python
import aiohttp
import asyncio

async def fetch_menu_data(url: str) -> dict:
    """Fetch menu data asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# In Azure Function
async def main(req: func.HttpRequest) -> func.HttpResponse:
    data = await fetch_menu_data(api_url)
    return func.HttpResponse(json.dumps(data))
```

## Enhanced Error Handling for Azure

```python
import logging
from typing import Optional
from azure.core.exceptions import (
    AzureError, 
    ResourceNotFoundError,
    HttpResponseError,
    ServiceRequestError
)
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ✅ Azure-specific error handling
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def fetch_from_azure_api(url: str) -> dict:
    """Fetch data with Azure-aware retry logic."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 429:  # Rate limit
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=429
                    )
                
                response.raise_for_status()
                return await response.json()
                
    except aiohttp.ClientConnectionError as e:
        logger.error(f"Connection failed to {url}: {e}")
        raise ServiceUnavailableError(f"External API unreachable: {url}") from e
    
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            logger.warning(f"Resource not found: {url}")
            return {}
        elif e.status >= 500:
            logger.error(f"Server error from {url}: {e.status}")
            raise ServiceError(f"External API error: {e.status}") from e
        else:
            logger.error(f"Client error from {url}: {e.status}")
            raise ClientError(f"Request failed: {e.status}") from e

# Azure SDK error handling
async def get_blob_content(container: str, blob_name: str) -> Optional[bytes]:
    """Get blob content with proper Azure error handling."""
    try:
        blob_client = blob_service.get_blob_client(
            container=container,
            blob=blob_name
        )
        
        download_stream = await blob_client.download_blob()
        return await download_stream.readall()
        
    except ResourceNotFoundError:
        logger.info(f"Blob not found: {container}/{blob_name}")
        return None
        
    except HttpResponseError as e:
        if e.status_code == 403:
            logger.error(f"Access denied to blob: {container}/{blob_name}")
            raise PermissionError("Insufficient permissions") from e
        else:
            logger.error(f"Azure HTTP error: {e.status_code} - {e.message}")
            raise AzureServiceError(f"Blob operation failed: {e.message}") from e
            
    except AzureError as e:
        logger.error(f"Azure SDK error: {e}")
        raise AzureServiceError(f"Azure operation failed: {str(e)}") from e

# ❌ Avoid - Generic exception handling
try:
    response = client.fetch_data()
except Exception as e:
    print(f"Error: {e}")  # No logging, no context, no retry
    pass
```

## Azure-Aware Logging and Observability

```python
import logging
import json
import os
from typing import Any, Dict
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

# Configure Azure Monitor integration
if app_insights_key := os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor(connection_string=app_insights_key)

# Get tracer
tracer = trace.get_tracer(__name__)

class AzureStructuredLogger:
    """Structured logger optimized for Azure Application Insights."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create formatter for structured logging
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler for local dev
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def info(self, message: str, **kwargs):
        """Log info with structured data."""
        extra_data = self._prepare_extra(kwargs)
        self.logger.info(message, extra=extra_data)
    
    def error(self, message: str, exception: Exception = None, **kwargs):
        """Log error with exception context."""
        extra_data = self._prepare_extra(kwargs)
        if exception:
            extra_data["exception_type"] = type(exception).__name__
            extra_data["exception_message"] = str(exception)
        
        self.logger.error(message, extra=extra_data, exc_info=exception)
    
    def _prepare_extra(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare extra data for Application Insights."""
        return {
            "custom_dimensions": {
                k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                for k, v in data.items()
            }
        }

# Usage in Azure Functions
logger = AzureStructuredLogger(__name__)

def main(req: func.HttpRequest) -> func.HttpResponse:
    with tracer.start_as_current_span("process_request") as span:
        correlation_id = req.headers.get("x-correlation-id", "unknown")
        batch_id = req.params.get("batch_id")
        
        # Add span attributes
        span.set_attribute("correlation_id", correlation_id)
        span.set_attribute("batch_id", batch_id)
        
        logger.info(
            "Processing batch request",
            correlation_id=correlation_id,
            batch_id=batch_id,
            user_agent=req.headers.get("user-agent"),
            function_name="process_batch"
        )
        
        try:
            result = process_batch(batch_id)
            
            logger.info(
                "Batch processed successfully",
                correlation_id=correlation_id,
                batch_id=batch_id,
                records_processed=result.count
            )
            
            return func.HttpResponse(
                json.dumps({"status": "success", "count": result.count}),
                status_code=200,
                headers={"x-correlation-id": correlation_id}
            )
            
        except Exception as e:
            logger.error(
                "Batch processing failed",
                exception=e,
                correlation_id=correlation_id,
                batch_id=batch_id
            )
            
            return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                headers={"x-correlation-id": correlation_id}
            )
```

## Project Structure

```
project/
├── src/
│   ├── __init__.py
│   ├── handlers/          # Azure Function handlers
│   │   ├── __init__.py
│   │   └── http_trigger.py
│   ├── services/          # Business logic
│   │   ├── __init__.py
│   │   └── batch_service.py
│   └── models/            # Data models
│       ├── __init__.py
│       └── batch.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   └── integration/
├── requirements.txt
├── pyproject.toml
└── host.json
```

## Required Azure Dependencies

```txt
# requirements.txt - Azure optimized
azure-functions>=1.17.0
azure-identity>=1.15.0
azure-storage-blob>=12.19.0
azure-keyvault-secrets>=4.7.0
azure-monitor-opentelemetry>=1.2.0

# Database
pymssql>=2.2.8                    # NOT pyodbc - Linux compatible
aiomysql>=0.2.0                   # For MySQL if needed

# HTTP and async
aiohttp>=3.9.0
httpx>=0.26.0                     # Modern HTTP client
tenacity>=8.2.0                   # Retry logic

# Auth and security
pyjwt[crypto]>=2.8.0
cryptography>=41.0.0

# Data processing
pydantic>=2.5.0                   # Data validation
orjson>=3.9.0                     # Fast JSON serialization

# Development tools
pytest>=7.4.0
pytest-asyncio>=0.21.0
black>=23.0.0
ruff>=0.1.0

# Optional: Specialized libraries
pandas>=2.1.0                     # Data analysis
numpy>=1.25.0                     # Numerical computing
requests>=2.31.0                  # Simple HTTP (when async not needed)
```

## Azure Container Apps Patterns

```python
# main.py for Container Apps
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

# Configure logging for Container Apps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global Azure clients (initialized once)
credential = None
blob_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Azure clients on startup."""
    global credential, blob_client
    
    logger.info("🚀 Starting Container App...")
    credential = DefaultAzureCredential()
    
    blob_client = BlobServiceClient(
        account_url=f"https://{os.environ['AZURE_STORAGE_ACCOUNT_NAME']}.blob.core.windows.net",
        credential=credential
    )
    
    logger.info("✅ Azure clients initialized")
    yield
    
    logger.info("🛑 Shutting down Container App...")

app = FastAPI(
    title="Terprint Service",
    version="1.0.0",
    lifespan=lifespan
)

# Dependency injection for Azure clients
def get_blob_client() -> BlobServiceClient:
    if blob_client is None:
        raise HTTPException(500, "Blob client not initialized")
    return blob_client

@app.get("/health")
async def health_check():
    """Health check endpoint for Container Apps."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "azure_credential": credential is not None,
        "blob_client": blob_client is not None
    }

@app.post("/process")
async def process_data(
    data: dict,
    blob_service: BlobServiceClient = Depends(get_blob_client)
):
    """Process data with Azure Blob Storage."""
    try:
        # Upload to blob
        container_client = blob_service.get_container_client("data")
        blob_client = container_client.get_blob_client("processed.json")
        
        await blob_client.upload_blob(
            json.dumps(data).encode(),
            overwrite=True
        )
        
        return {"status": "success", "message": "Data processed"}
    
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise HTTPException(500, f"Processing failed: {str(e)}")
```

## Testing Azure Components

```python
# tests/unit/test_azure_service.py
import pytest
from unittest.mock import AsyncMock, Mock, patch
from azure.core.exceptions import ResourceNotFoundError
from src.services.azure_service import AzureDataService

class TestAzureDataService:
    """Test Azure service with proper mocking."""
    
    @pytest.fixture
    def mock_blob_client(self):
        """Mock Azure Blob client."""
        mock_client = Mock()
        mock_client.download_blob = AsyncMock()
        mock_client.upload_blob = AsyncMock()
        return mock_client
    
    @pytest.fixture
    def azure_service(self, mock_blob_client):
        """Create service with mocked dependencies."""
        with patch('src.services.azure_service.BlobServiceClient') as mock_blob_service:
            mock_blob_service.return_value.get_blob_client.return_value = mock_blob_client
            service = AzureDataService()
            service.blob_client = mock_blob_client
            return service
    
    @pytest.mark.asyncio
    async def test_fetch_data_returns_content_when_blob_exists(self, azure_service, mock_blob_client):
        """Test successful data fetch."""
        # Arrange
        expected_data = b'{"test": "data"}'
        mock_download = AsyncMock()
        mock_download.readall = AsyncMock(return_value=expected_data)
        mock_blob_client.download_blob.return_value = mock_download
        
        # Act
        result = await azure_service.fetch_data("container", "blob.json")
        
        # Assert
        assert result == expected_data
        mock_blob_client.download_blob.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_data_returns_none_when_blob_not_found(self, azure_service, mock_blob_client):
        """Test handling of missing blob."""
        # Arrange
        mock_blob_client.download_blob.side_effect = ResourceNotFoundError("Blob not found")
        
        # Act
        result = await azure_service.fetch_data("container", "missing.json")
        
        # Assert
        assert result is None
    
    @pytest.mark.asyncio
    async def test_upload_data_handles_retry_logic(self, azure_service, mock_blob_client):
        """Test retry logic for transient failures."""
        # Arrange
        mock_blob_client.upload_blob.side_effect = [
            Exception("Transient error"),
            Exception("Another transient error"),
            None  # Success on third attempt
        ]
        
        # Act & Assert
        await azure_service.upload_data(b"test data", "container", "test.json")
        assert mock_blob_client.upload_blob.call_count == 3

# tests/integration/test_azure_integration.py
@pytest.mark.integration
@pytest.mark.asyncio
class TestAzureIntegration:
    """Integration tests against real Azure services."""
    
    @pytest.fixture(scope="session")
    async def azure_config(self):
        """Load test configuration."""
        return AzureConfig.from_env()
    
    async def test_blob_storage_roundtrip(self, azure_config):
        """Test actual blob storage operations."""
        from azure.storage.blob.aio import BlobServiceClient
        from azure.identity.aio import DefaultAzureCredential
        
        credential = DefaultAzureCredential()
        test_data = b'{"test": "integration"}'
        test_blob = f"test-{uuid.uuid4()}.json"
        
        async with BlobServiceClient(
            account_url=azure_config.storage_account_url,
            credential=credential
        ) as blob_service:
            # Upload
            blob_client = blob_service.get_blob_client(
                container="test-container",
                blob=test_blob
            )
            await blob_client.upload_blob(test_data, overwrite=True)
            
            # Download
            download_stream = await blob_client.download_blob()
            downloaded_data = await download_stream.readall()
            
            # Verify
            assert downloaded_data == test_data
            
            # Cleanup
            await blob_client.delete_blob()
    
    async def test_key_vault_secret_retrieval(self, azure_config):
        """Test Key Vault secret access."""
        if not azure_config.key_vault_url:
            pytest.skip("Key Vault not configured")
        
        from azure.keyvault.secrets.aio import SecretClient
        from azure.identity.aio import DefaultAzureCredential
        
        credential = DefaultAzureCredential()
        
        async with SecretClient(
            vault_url=azure_config.key_vault_url,
            credential=credential
        ) as vault_client:
            # This assumes a test secret exists
            secret = await vault_client.get_secret("test-secret")
            assert secret.value is not None

# pytest configuration (pytest.ini)
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (require Azure resources)
    slow: Slow tests that may take several seconds
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    -m "not integration"  # Skip integration tests by default

# Run commands
# pytest                        # Unit tests only
# pytest -m integration         # Integration tests only
# pytest --cov=src             # With coverage
```

## Enhanced Configuration Management

```python
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os
import json
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

@dataclass(frozen=True)
class AzureConfig:
    """Azure-aware configuration with Key Vault integration."""
    
    # Required Azure settings
    tenant_id: str
    subscription_id: str
    resource_group: str
    
    # Storage settings
    storage_account_name: str
    storage_container_name: str = "jsonfiles"
    
    # Database settings
    database_server: str
    database_name: str
    
    # Key Vault
    key_vault_name: Optional[str] = None
    key_vault_url: Optional[str] = None
    
    # Application settings
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Runtime configuration
    max_workers: int = 10
    timeout_seconds: int = 30
    retry_attempts: int = 3
    
    # Derived properties
    storage_account_url: str = field(init=False)
    database_connection_string: str = field(init=False)
    
    def __post_init__(self):
        # Set derived properties
        object.__setattr__(
            self, 
            'storage_account_url', 
            f"https://{self.storage_account_name}.blob.core.windows.net"
        )
        
        object.__setattr__(
            self,
            'database_connection_string',
            f"Server={self.database_server}.database.windows.net;"
            f"Database={self.database_name};"
            f"Authentication=ActiveDirectoryDefault"
        )
        
        if self.key_vault_name and not self.key_vault_url:
            object.__setattr__(
                self,
                'key_vault_url',
                f"https://{self.key_vault_name}.vault.azure.net"
            )
    
    @classmethod
    def from_env(cls) -> "AzureConfig":
        """Load configuration from environment variables."""
        return cls(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
            resource_group=os.environ["AZURE_RESOURCE_GROUP"],
            storage_account_name=os.environ["AZURE_STORAGE_ACCOUNT_NAME"],
            storage_container_name=os.environ.get("AZURE_CONTAINER_NAME", "jsonfiles"),
            database_server=os.environ["DATABASE_SERVER"],
            database_name=os.environ["DATABASE_NAME"],
            key_vault_name=os.environ.get("KEY_VAULT_NAME"),
            environment=os.environ.get("ENVIRONMENT", "development"),
            debug=os.environ.get("DEBUG", "false").lower() == "true",
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            max_workers=int(os.environ.get("MAX_WORKERS", "10")),
            timeout_seconds=int(os.environ.get("TIMEOUT_SECONDS", "30")),
            retry_attempts=int(os.environ.get("RETRY_ATTEMPTS", "3"))
        )
    
    @classmethod
    async def from_key_vault(cls, base_config: "AzureConfig") -> "AzureConfig":
        """Enhance configuration with Key Vault secrets."""
        if not base_config.key_vault_url:
            return base_config
        
        try:
            credential = DefaultAzureCredential()
            vault_client = SecretClient(
                vault_url=base_config.key_vault_url,
                credential=credential
            )
            
            # Load secrets (non-blocking pattern)
            secrets = {}
            secret_names = ["database-password", "api-keys", "connection-strings"]
            
            for secret_name in secret_names:
                try:
                    secret = vault_client.get_secret(secret_name)
                    secrets[secret_name.replace("-", "_")] = secret.value
                except Exception:
                    # Secret doesn't exist or no permission - continue
                    pass
            
            # Create new config with secrets
            config_dict = base_config.__dict__.copy()
            config_dict.update(secrets)
            
            return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})
            
        except Exception as e:
            # Log warning but continue with base config
            logging.warning(f"Failed to load Key Vault secrets: {e}")
            return base_config

# Global configuration instance
config: Optional[AzureConfig] = None

async def get_config() -> AzureConfig:
    """Get application configuration (singleton pattern)."""
    global config
    if config is None:
        base_config = AzureConfig.from_env()
        config = await AzureConfig.from_key_vault(base_config)
    return config

# Usage examples
async def example_usage():
    cfg = await get_config()
    
    # Use in blob operations
    blob_client = BlobServiceClient(
        account_url=cfg.storage_account_url,
        credential=DefaultAzureCredential()
    )
    
    # Use in database operations
    conn = pymssql.connect(
        server=f"{cfg.database_server}.database.windows.net",
        database=cfg.database_name
    )
```

## Code Style & Quality Standards

- Follow **PEP 8** with these Azure-specific additions:
- Use **black** for code formatting (`black --line-length 100`)
- Use **ruff** for fast linting (`ruff check --fix`)
- Maximum line length: **100 characters** (Azure function names can be long)
- Use **f-strings** for string formatting (Python 3.6+ requirement)
- Use **type hints** for all function signatures
- Prefer **async/await** for I/O operations
- Use **pathlib** instead of os.path for file operations

### Azure-Specific Style Guide

```python
# ✅ CORRECT - Azure naming conventions
async def download_trulieve_menu_data(
    store_location: str,
    category_id: str,
    blob_container: str = "dispensaries"
) -> Optional[Dict[str, Any]]:
    """
    Download menu data for a specific Trulieve store location.
    
    Args:
        store_location: Store location identifier (e.g., 'orlando')
        category_id: Product category ID from Trulieve API
        blob_container: Azure blob container name
        
    Returns:
        Menu data dict or None if not found
        
    Raises:
        AzureServiceError: If Azure services are unavailable
        ValidationError: If input parameters are invalid
    """
    pass

# ✅ CORRECT - Resource management with async context managers
async def process_all_stores(stores: List[str]) -> Dict[str, ProcessResult]:
    """Process menu data for all stores with proper resource management."""
    results = {}
    
    credential = DefaultAzureCredential()
    
    async with BlobServiceClient(
        account_url="https://storage.blob.core.windows.net",
        credential=credential
    ) as blob_service:
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        ) as session:
            
            tasks = [
                process_store(store, session, blob_service)
                for store in stores
            ]
            
            completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for store, result in zip(stores, completed_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to process {store}: {result}")
                    results[store] = ProcessResult(success=False, error=str(result))
                else:
                    results[store] = result
    
    return results

# ❌ AVOID - Blocking calls in async functions
async def bad_example():
    # Don't mix sync and async
    time.sleep(5)  # Blocks the event loop
    response = requests.get(url)  # Blocking HTTP call
    
    # Use these instead:
    await asyncio.sleep(5)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

# ✅ CORRECT - Proper exception chaining and context
def handle_azure_errors(func):
    """Decorator for consistent Azure error handling."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ResourceNotFoundError as e:
            logger.warning(f"Resource not found in {func.__name__}: {e}")
            return None
        except HttpResponseError as e:
            logger.error(f"Azure HTTP error in {func.__name__}: {e.status_code} - {e.message}")
            raise AzureServiceError(f"Operation failed: {e.message}") from e
        except AzureError as e:
            logger.error(f"Azure SDK error in {func.__name__}: {e}")
            raise AzureServiceError(f"Azure operation failed: {str(e)}") from e
    return wrapper
```

## Development Workflow

1. **Environment Setup**
   ```bash
   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -e .
   
   # Install development tools
   pip install black ruff pytest pytest-asyncio pytest-cov
   ```

2. **Code Quality Checks**
   ```bash
   # Format code
   black --line-length 100 src/ tests/
   
   # Lint code
   ruff check --fix src/ tests/
   
   # Type checking (optional)
   mypy src/
   ```

3. **Testing**
   ```bash
   # Unit tests only (fast)
   pytest -m "not integration"
   
   # All tests including integration
   pytest
   
   # With coverage
   pytest --cov=src --cov-report=html
   ```

4. **Azure Development**
   ```bash
   # Azure CLI login for local development
   az login
   
   # Set subscription
   az account set --subscription "your-subscription-id"
   
   # Test Azure Functions locally
   func host start --port 7071
   
   # Deploy to Azure
   func azure functionapp publish your-function-app
   ```

This enhanced Python instruction set provides comprehensive guidance for Azure development, addressing the issues we've encountered with Container Apps, Azure Functions, authentication, error handling, and proper async patterns.
