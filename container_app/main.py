"""
Terprint Menu Downloader - Container App Version
FastAPI-based container app with APScheduler for scheduled downloads.

Replaces the Azure Function with a container-native approach.
"""
import os
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import stock routes
try:
    from stock_routes import router as stock_router
    STOCK_ROUTES_AVAILABLE = True
except ImportError:
    STOCK_ROUTES_AVAILABLE = False
    stock_router = None

# Ensure writable directories for logs in container environment
# Set log directory before any package imports that might try to create logs
os.environ.setdefault('LOG_DIR', '/tmp/logs')
os.environ.setdefault('TEMP', '/tmp')
os.makedirs('/tmp/logs', exist_ok=True)

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration from terprint-config
try:
    from terprint_config import (
        load_config_to_env, 
        get_logging_config,
        get_storage_config,
        get_batch_processor_trigger,
        get_available_dispensaries,
        get_shared_app_insights_connection_string
    )
    load_config_to_env()
    logging_config = get_logging_config('container_app')
    storage_config = get_storage_config()
    batch_processor_config = get_batch_processor_trigger()
    TERPRINT_CONFIG_AVAILABLE = True
    logger.info("terprint-config loaded successfully")
except ImportError as e:
    logger.warning(f"terprint-config not available: {e}")
    logging_config = None
    storage_config = None
    batch_processor_config = None
    TERPRINT_CONFIG_AVAILABLE = False

# Configure Azure Monitor OpenTelemetry
try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    app_insights_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if app_insights_conn:
        configure_azure_monitor(connection_string=app_insights_conn)
        logger.info("Azure Monitor OpenTelemetry configured")
except Exception as e:
    logger.warning(f"Azure Monitor configuration failed: {e}")

# Configuration from environment or terprint-config
STRAIN_INDEX_BLOB_NAME = "strain_index.json"
if TERPRINT_CONFIG_AVAILABLE and storage_config:
    STRAIN_INDEX_CONTAINER = storage_config.get('container_name', 'jsonfiles')
else:
    STRAIN_INDEX_CONTAINER = os.environ.get("AZURE_STORAGE_CONTAINER", "jsonfiles")

# Batch processor configuration
if TERPRINT_CONFIG_AVAILABLE and batch_processor_config:
    _bp_endpoint = batch_processor_config.get('endpoint', {})
    BATCH_PROCESSOR_URL = _bp_endpoint.get('url', 
        "https://ca-terprint-batchprocessor.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/run-batch-processor")
    BATCH_PROCESSOR_KEY = _bp_endpoint.get('code', '') or os.environ.get("BATCH_PROCESSOR_KEY", "")
else:
    BATCH_PROCESSOR_URL = os.environ.get(
        "BATCH_PROCESSOR_URL",
        "https://ca-terprint-batchprocessor.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/run-batch-processor"
    )
    BATCH_PROCESSOR_KEY = os.environ.get("BATCH_PROCESSOR_KEY", "")

# Global state for tracking
app_state = {
    "last_run": None,
    "last_run_status": None,
    "last_run_result": None,
    "is_running": False,
    "startup_time": None,
    "scheduled_runs": 0,
    "manual_runs": 0
}

# Scheduler instance
scheduler = AsyncIOScheduler()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class RunRequest(BaseModel):
    skip_batch_processor: bool = False
    dry_run_batch: bool = False
    dispensary: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    uptime_seconds: float
    last_run: Optional[str]
    last_run_status: Optional[str]
    is_running: bool
    scheduled_runs: int
    manual_runs: int
    next_scheduled_run: Optional[str]
    terprint_config_available: bool


class BatchTriggerRequest(BaseModel):
    dry_run: bool = False
    dispensary: Optional[str] = None


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def get_blob_service_client():
    """Get Azure Blob Service Client using managed identity or connection string."""
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    
    if TERPRINT_CONFIG_AVAILABLE and storage_config:
        account_name = storage_config.get('storage_account_name', 'storageacidnidatamover')
    else:
        account_name = os.environ.get("AZURE_STORAGE_ACCOUNT", "storageacidnidatamover")
    
    # Use managed identity (DefaultAzureCredential) in Azure Container Apps
    try:
        credential = DefaultAzureCredential()
        account_url = f"https://{account_name}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=credential)
    except Exception as e:
        logger.warning(f"Managed identity auth failed, trying connection string: {e}")
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if conn_str:
            return BlobServiceClient.from_connection_string(conn_str)
        raise ValueError("No valid Azure Storage credentials found")


def trigger_batch_processor(dry_run: bool = False, dispensary: str = None) -> dict:
    """Trigger the batch processor to process uploaded menu data."""
    if not BATCH_PROCESSOR_KEY:
        logger.warning("BATCH_PROCESSOR_KEY not configured, skipping batch processor trigger")
        return {"status": "skipped", "reason": "BATCH_PROCESSOR_KEY not configured"}
    
    url = f"{BATCH_PROCESSOR_URL}?code={BATCH_PROCESSOR_KEY}"
    payload = {"dry_run": dry_run}
    if dispensary:
        payload["dispensary"] = dispensary
    
    logger.info(f"Triggering batch processor at {BATCH_PROCESSOR_URL} (dry_run={dry_run}, dispensary={dispensary})")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Batch processor completed: {result.get('status', 'unknown')}")
        return {"status": "success", "response": result}
        
    except requests.exceptions.Timeout:
        logger.error("Batch processor request timed out")
        return {"status": "timeout", "error": "Request timed out after 300 seconds"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to trigger batch processor: {str(e)}")
        return {"status": "error", "error": str(e)}


def run_download() -> dict:
    """Run the menu download using the terprint-menu-downloader package."""
    from terprint_menu_downloader import DispensaryOrchestrator
    
    logger.info("Creating DispensaryOrchestrator...")
    logger.info("IMPORTANT: dev_mode=False - Using ALL PRODUCTION STORES")
    orchestrator = DispensaryOrchestrator(
        output_dir='/tmp/downloads',  # Use temp directory
        dev_mode=False,
        in_memory=True
    )
    
    # Log Trulieve configuration after orchestrator creation
    try:
        trulieve_config = orchestrator.downloaders.get('trulieve', {})
        if trulieve_config:
            downloader = trulieve_config.get('downloader')
            if downloader:
                store_count = len(getattr(downloader, 'store_ids', [])) if hasattr(downloader, 'store_ids') and downloader.store_ids else 0
                category_count = len(getattr(downloader, 'category_ids', [])) if hasattr(downloader, 'category_ids') and downloader.category_ids else 0
                logger.info(f"TRULIEVE CONFIG: {store_count} stores, {category_count} categories, total combinations: {store_count * category_count}")
                if store_count < 100:
                    logger.warning(f"WARNING: Only {store_count} Trulieve stores loaded - expected 162!")
    except Exception as e:
        logger.error(f"Error checking Trulieve config: {e}")
    
    logger.info("Running full pipeline...")
    results = orchestrator.run_full_pipeline(
        parallel_downloads=False,  # Sequential for stability
        upload_to_azure=True
    )
    
    return results


async def scheduled_download_job():
    """Background job for scheduled menu downloads."""
    global app_state
    
    if app_state["is_running"]:
        logger.warning("Download already in progress, skipping scheduled run")
        return
    
    app_state["is_running"] = True
    app_state["last_run"] = datetime.utcnow().isoformat()
    app_state["scheduled_runs"] += 1
    
    logger.info(f"Scheduled menu download triggered at {app_state['last_run']}")
    
    try:
        result = run_download()
        success_val = result.get('summary', {}).get('overall_success', False)
        success = success_val if isinstance(success_val, bool) else str(success_val).lower() == 'true'
        
        app_state["last_run_status"] = "success" if success else "partial"
        app_state["last_run_result"] = result.get('summary', {})
        
        logger.info(f"Scheduled download completed. Success: {success}")
        
        # Trigger batch processor
        logger.info("Triggering batch processor after download...")
        try:
            batch_result = trigger_batch_processor(dry_run=False)
            logger.info(f"Batch processor result: {batch_result.get('status', 'unknown')}")
        except Exception as batch_err:
            logger.error(f"Batch processor trigger failed: {str(batch_err)}")
            
    except Exception as e:
        logger.error(f"Scheduled download failed: {str(e)}", exc_info=True)
        app_state["last_run_status"] = "error"
        app_state["last_run_result"] = {"error": str(e)}
        
        # Still try batch processor
        try:
            trigger_batch_processor(dry_run=False)
        except Exception:
            pass
    finally:
        app_state["is_running"] = False


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    app_state["startup_time"] = datetime.utcnow()
    logger.info("Starting Terprint Menu Downloader Container App...")
    
    # Schedule downloads every 2 hours from 8am-10pm EST (13:00-03:00 UTC)
    # Runs at: 8am, 10am, 12pm, 2pm, 4pm, 6pm, 8pm, 10pm EST
    scheduler.add_job(
        scheduled_download_job,
        CronTrigger(hour='1,3,13,15,17,19,21,23', minute=0, timezone='UTC'),
        id='scheduled_download',
        name='Menu Download Job',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started with cron: 0 2,14,20 * * * (UTC)")
    
    yield
    
    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shutdown complete")


app = FastAPI(
    title="Terprint Menu Downloader",
    description="Container App for downloading dispensary menus and uploading to Azure Data Lake",
    version="2.0.0",
    lifespan=lifespan
)

# Include stock routes if available
if STOCK_ROUTES_AVAILABLE and stock_router:
    app.include_router(stock_router)
    logger.info('Stock routes enabled')
else:
    logger.warning('Stock routes not available - terprint-core package may be missing')



# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for Container Apps probes."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get detailed status of the menu downloader."""
    uptime = (datetime.utcnow() - app_state["startup_time"]).total_seconds() if app_state["startup_time"] else 0
    
    # Get next scheduled run time
    next_run = None
    job = scheduler.get_job('scheduled_download')
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()
    
    return StatusResponse(
        status="running" if app_state["is_running"] else "idle",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=uptime,
        last_run=app_state["last_run"],
        last_run_status=app_state["last_run_status"],
        is_running=app_state["is_running"],
        scheduled_runs=app_state["scheduled_runs"],
        manual_runs=app_state["manual_runs"],
        next_scheduled_run=next_run,
        terprint_config_available=TERPRINT_CONFIG_AVAILABLE
    )


@app.post("/run")
async def manual_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Trigger a manual menu download."""
    if app_state["is_running"]:
        raise HTTPException(status_code=409, detail="Download already in progress")
    
    app_state["is_running"] = True
    app_state["last_run"] = datetime.utcnow().isoformat()
    app_state["manual_runs"] += 1
    
    logger.info(f"Manual menu download triggered at {app_state['last_run']}")
    
    try:
        result = run_download()
        success_val = result.get('summary', {}).get('overall_success', False)
        success = success_val if isinstance(success_val, bool) else str(success_val).lower() == 'true'
        
        app_state["last_run_status"] = "success" if success else "partial"
        app_state["last_run_result"] = result.get('summary', {})
        
        # Trigger batch processor unless skipped
        batch_result = None
        if not request.skip_batch_processor:
            batch_result = trigger_batch_processor(
                dry_run=request.dry_run_batch,
                dispensary=request.dispensary
            )
        
        return {
            "status": "completed",
            "download_result": result.get('summary', {}),
            "batch_processor_result": batch_result
        }
        
    except Exception as e:
        logger.error(f"Manual download failed: {str(e)}", exc_info=True)
        app_state["last_run_status"] = "error"
        app_state["last_run_result"] = {"error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        app_state["is_running"] = False


@app.post("/trigger-batch-processor")
async def trigger_batch(request: BatchTriggerRequest):
    """Manually trigger the batch processor."""
    result = trigger_batch_processor(
        dry_run=request.dry_run,
        dispensary=request.dispensary
    )
    return result


@app.get("/config")
async def get_config():
    """Get current configuration (non-sensitive)."""
    return {
        "terprint_config_available": TERPRINT_CONFIG_AVAILABLE,
        "batch_processor_url": BATCH_PROCESSOR_URL,
        "batch_processor_configured": bool(BATCH_PROCESSOR_KEY),
        "strain_index_container": STRAIN_INDEX_CONTAINER,
        "scheduler_running": scheduler.running,
        "scheduled_jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
            for job in scheduler.get_jobs()
        ]
    }


# Run with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

