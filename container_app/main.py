"""
Terprint Menu Downloader - Container App Version
FastAPI-based container app with configurable modes:

DEPLOYMENT MODES:
1. API-Only Mode (default):
   - Environment: TERPRINT_RUN_MODE=api-only (or not set)
   - Purpose: Stock checking, manual endpoints, health checks
   - Lightweight, always available
   - No scheduled downloads
   
2. Scheduler Mode:
   - Environment: TERPRINT_RUN_MODE=scheduler  
   - Purpose: Automated menu downloads (3x daily)
   - Heavier workload, periodic execution
   - Includes all API endpoints plus scheduling

RECOMMENDED ARCHITECTURE:
- Deploy separate container apps for each mode
- API container: Always running, handles user requests
- Scheduler container: Handles automated downloads
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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Import stock routes
try:
    from .stock_routes import router as stock_router
    STOCK_ROUTES_AVAILABLE = True
except ImportError:
    try:
        # Fallback for direct execution
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from stock_routes import router as stock_router
        STOCK_ROUTES_AVAILABLE = True
    except ImportError:
        STOCK_ROUTES_AVAILABLE = False
        stock_router = None

# Import stock indexer for building index after downloads
try:
    from .stock_indexer import StockIndexer
    STOCK_INDEXER_AVAILABLE = True
except ImportError:
    try:
        # Fallback for direct execution
        from stock_indexer import StockIndexer
        STOCK_INDEXER_AVAILABLE = True
    except ImportError:
        STOCK_INDEXER_AVAILABLE = False
        StockIndexer = None

# Import notifications for pipeline stage emails
try:
    from .notifications import notify_stage_start, notify_stage_complete, notify_pipeline_summary
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    try:
        from notifications import notify_stage_start, notify_stage_complete, notify_pipeline_summary
        NOTIFICATIONS_AVAILABLE = True
    except ImportError:
        NOTIFICATIONS_AVAILABLE = False
        notify_stage_start = lambda *args, **kwargs: False
        notify_stage_complete = lambda *args, **kwargs: False
        notify_pipeline_summary = lambda *args, **kwargs: False

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

# Batch Creator configuration (Stage 2.5 - creates consolidated batch files)
BATCH_CREATOR_URL = os.environ.get(
    "BATCH_CREATOR_URL",
    "https://ca-terprint-batches.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/create-batches"
)

# Batch processor configuration (Stage 3 - processes COAs from batch files)
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


def trigger_batch_creator(trigger_coa: bool = True) -> dict:
    """Trigger the Batch Creator to consolidate menu files into batch files.
    
    Args:
        trigger_coa: If True, Batch Creator will automatically trigger COA Processor after batch creation
    
    Returns:
        dict with status and response from Batch Creator
    """
    logger.info(f"Triggering Batch Creator at {BATCH_CREATOR_URL} (trigger_coa={trigger_coa})")
    
    try:
        # Call Batch Creator - it will process today's menus by default
        response = requests.post(
            BATCH_CREATOR_URL,
            params={"trigger_coa": trigger_coa},
            headers={"Content-Type": "application/json"},
            timeout=600  # Batch creation can take a while
        )
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Batch Creator completed: {result.get('status', 'unknown')}")
        return {"status": "success", "response": result}
        
    except requests.exceptions.Timeout:
        logger.error("Batch Creator request timed out")
        return {"status": "timeout", "error": "Request timed out after 600 seconds"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to trigger Batch Creator: {str(e)}")
        return {"status": "error", "error": str(e)}


def trigger_batch_processor(dry_run: bool = False, dispensary: str = None, date: str = None) -> dict:
    """Trigger the batch processor to process uploaded menu data.
    
    Args:
        dry_run: If True, run in dry-run mode without writing to database
        dispensary: Specific dispensary to process (optional)
        date: Date to process in YYYY-MM-DD format (defaults to today)
    """
    if not BATCH_PROCESSOR_KEY:
        logger.warning("BATCH_PROCESSOR_KEY not configured, skipping batch processor trigger")
        return {"status": "skipped", "reason": "BATCH_PROCESSOR_KEY not configured"}
    
    url = f"{BATCH_PROCESSOR_URL}?code={BATCH_PROCESSOR_KEY}"
    payload = {"dry_run": dry_run}
    if dispensary:
        payload["dispensary"] = dispensary
    if date:
        payload["date"] = date
    
    logger.info(f"Triggering batch processor at {BATCH_PROCESSOR_URL} (dry_run={dry_run}, dispensary={dispensary}, date={date})")
    
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


def build_stock_index_from_menus() -> dict:
    """
    Build stock index v2 from all dispensary menu files + SQL enrichment + genetics.
    Called automatically after each menu download run.
    """
    if not STOCK_INDEXER_AVAILABLE:
        logger.warning("Stock indexer not available - skipping index build")
        return {"success": False, "error": "Stock indexer not available"}

    try:
        logger.info("Building stock index v2 from menu data + SQL + genetics...")
        indexer = StockIndexer()

        # v2: build_index() scans ALL dispensary menus, enriches with SQL + genetics
        index = indexer.build_index()

        if index and index.get("metadata", {}).get("total_items", 0) > 0:
            path = indexer.save_index(index)
            metadata = index["metadata"]
            logger.info(
                f"Stock index v2 built: {metadata['total_items']} items, "
                f"{metadata['unique_strains']} strains, "
                f"{len(metadata.get('dispensaries', {}))} dispensaries"
            )
            return {
                "success": True,
                "total_items": metadata["total_items"],
                "unique_strains": metadata["unique_strains"],
                "dispensaries": metadata.get("dispensaries", {}),
                "enrichment": metadata.get("enrichment", {}),
                "index_path": path,
            }
        else:
            logger.warning("No items found for stock index - menu files may not exist yet")
            return {"success": False, "error": "No menu data available yet"}

    except Exception as e:
        logger.error(f"Failed to build stock index: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


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
    """Background job for scheduled menu downloads with email notifications.

    IMPORTANT: All heavy sync operations run via asyncio.to_thread() so the
    FastAPI event loop stays responsive for health checks and API requests.
    """
    import asyncio
    import time
    global app_state
    
    pipeline_results = {}

    if app_state["is_running"]:
        logger.warning("Download already in progress, skipping scheduled run")
        return

    app_state["is_running"] = True
    app_state["last_run"] = datetime.utcnow().isoformat()
    app_state["scheduled_runs"] += 1

    logger.info(f"Scheduled menu download triggered at {app_state['last_run']}")

    try:
        # ===== STAGE 1: Menu Download (sync → thread) =====
        download_start = time.time()
        notify_stage_start('download', {'trigger': 'scheduled', 'run_number': app_state['scheduled_runs']})
        
        result = await asyncio.to_thread(run_download)
        success_val = result.get('summary', {}).get('overall_success', False)
        success = success_val if isinstance(success_val, bool) else str(success_val).lower() == 'true'

        app_state["last_run_status"] = "success" if success else "partial"
        app_state["last_run_result"] = result.get('summary', {})
        
        download_duration = time.time() - download_start
        notify_stage_complete('download', success, result.get('summary', {}), download_duration)
        pipeline_results['download_result'] = {'success': success, 'summary': result.get('summary', {})}

        logger.info(f"Scheduled download completed. Success: {success}")

        # ===== STAGE 2: COA Processor (sync → thread) =====
        logger.info("Triggering Batch Processor for COA extraction...")
        coa_start = time.time()
        notify_stage_start('coa_process', {'date': datetime.now().strftime('%Y-%m-%d')})
        
        batch_processor_result = {'status': 'skipped'}
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            batch_processor_result = await asyncio.to_thread(trigger_batch_processor, date=today)
            coa_success = batch_processor_result.get('status') == 'success'
            logger.info(f"Batch Processor result: {batch_processor_result.get('status', 'unknown')}")
        except Exception as batch_err:
            logger.error(f"Batch Processor trigger failed: {str(batch_err)}")
            batch_processor_result = {'status': 'error', 'error': str(batch_err)}
            coa_success = False
        
        coa_duration = time.time() - coa_start
        notify_stage_complete('coa_process', coa_success, batch_processor_result, coa_duration)
        pipeline_results['coa_process_result'] = batch_processor_result

        # ===== STAGE 3: Stock Index Build (sync → thread) =====
        logger.info("Building stock index from consolidated batches...")
        index_start = time.time()
        notify_stage_start('stock_index')
        
        index_result = {'success': False, 'error': 'Not attempted'}
        try:
            index_result = await asyncio.to_thread(build_stock_index_from_menus)
            if index_result.get('success'):
                logger.info(f"Stock index built: {index_result.get('total_items', 0)} items")
            else:
                logger.warning(f"Stock index build issue: {index_result.get('error')}")
        except Exception as index_err:
            logger.error(f"Stock index build failed: {str(index_err)}")
            index_result = {'success': False, 'error': str(index_err)}
        
        index_duration = time.time() - index_start
        notify_stage_complete('stock_index', index_result.get('success', False), index_result, index_duration)
        pipeline_results['stock_index_result'] = index_result
        
        # Send pipeline summary
        pipeline_results['summary'] = app_state['last_run_result']
        notify_pipeline_summary(pipeline_results)

    except Exception as e:
        logger.error(f"Scheduled download failed: {str(e)}", exc_info=True)
        app_state["last_run_status"] = "error"
        app_state["last_run_result"] = {"error": str(e)}
        notify_stage_complete('download', False, {'error': str(e)})

    finally:
        app_state["is_running"] = False
        # Always try to create batches even if download failed (may have partial data)
        if app_state["last_run_status"] == "error":
            try:
                logger.info("Download failed but attempting batch creation anyway...")
                trigger_batch_creator(trigger_coa=True)
            except Exception:
                pass



# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    app_state["startup_time"] = datetime.utcnow()
    
    # Check if this should run as API-only or with scheduler
    run_mode = os.environ.get("TERPRINT_RUN_MODE", "api-only").lower()
    
    if run_mode == "scheduler":
        logger.info("Starting Terprint Menu Downloader in SCHEDULER mode...")
        
        # Schedule downloads more conservatively:
        # - 9:00 AM EST (2:00 PM UTC) - Morning run
        # - 3:00 PM EST (8:00 PM UTC) - Afternoon run  
        # - 9:00 PM EST (2:00 AM UTC) - Evening run
        # This gives 6-hour intervals and avoids overwhelming dispensary APIs
        scheduler.add_job(
            scheduled_download_job,
            CronTrigger(hour='13,15,17,19,21,23,1,3', minute=0, timezone='UTC'),
            id='scheduled_download',
            name='Menu Download Job (every 2hrs 8am-10pm EST)',
            replace_existing=True
        )
        scheduler.start()
        logger.info("âœ… SCHEDULER MODE: Menu downloads will run every 2 hours from 8am-10pm EST")
        logger.info("ðŸ“‹ No downloads at startup - waiting for scheduled times")
        
    else:  # api-only mode (default)
        logger.info("Starting Terprint Menu Downloader in API-ONLY mode...")
        logger.info("âœ… API-ONLY MODE: Stock checking and manual endpoints available")
        logger.info("ðŸ“‹ No scheduled downloads - use separate scheduler container for automation")
        logger.info("ðŸ”— Manual downloads available via POST /run endpoint")
    
    yield
    
    # Shutdown
    run_mode = os.environ.get("TERPRINT_RUN_MODE", "api-only").lower()
    if run_mode == "scheduler" and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler shutdown complete")
    else:
        logger.info("API-only mode shutdown - no scheduler to stop")


app = FastAPI(
    title="Terprint Menu Downloader",
    description="Container App for downloading dispensary menus and uploading to Azure Data Lake",
    version="2.0.0",
    lifespan=lifespan
)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================
# Configure CORS to allow requests from:
# 1. Local development (localhost:3000, localhost:8080, etc.)
# 2. APIM gateway (apim-terprint-dev.azure-api.net)
# 3. Terprint web app (terprint.acidni.net)
# 4. Container app direct access (for testing)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Development
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8080",
        # Production/APIM
        "https://apim-terprint-dev.azure-api.net",
        "https://apim-terprint.azure-api.net",
        # Web app
        "https://terprint.acidni.net",
        "https://terprint-web.azurewebsites.net",
        # Container app (for testing)
        "https://ca-terprint-menudownloader.kindmoss-c6723cbe.eastus2.azurecontainerapps.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["content-length", "x-json-response-size", "content-type"],
    max_age=86400,  # Cache CORS preflight for 24 hours
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
    run_mode = os.environ.get("TERPRINT_RUN_MODE", "api-only").lower()
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow().isoformat(),
        "mode": run_mode,
        "scheduler_active": scheduler.running if run_mode == "scheduler" else False
    }


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get detailed status of the menu downloader."""
    uptime = (datetime.utcnow() - app_state["startup_time"]).total_seconds() if app_state["startup_time"] else 0
    run_mode = os.environ.get("TERPRINT_RUN_MODE", "api-only").lower()
    
    # Get next scheduled run time (only in scheduler mode)
    next_run = None
    if run_mode == "scheduler":
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
    """
    Trigger a manual menu download (MANUAL OVERRIDE).
    
    IMPORTANT: This bypasses the scheduled downloads and should only be used for:
    - Testing and development
    - Emergency data recovery
    - One-off backfills
    
    Normal operation uses scheduled downloads (3x daily).
    """
    if app_state["is_running"]:
        raise HTTPException(status_code=409, detail="Download already in progress")
    
    logger.warning("ðŸš¨ MANUAL DOWNLOAD TRIGGERED - This overrides the normal schedule!")
    
    app_state["is_running"] = True
    app_state["last_run"] = datetime.utcnow().isoformat()
    app_state["manual_runs"] += 1
    
    logger.info(f"Manual menu download triggered at {app_state['last_run']}")
    
    try:
        import asyncio
        result = await asyncio.to_thread(run_download)
        success_val = result.get('summary', {}).get('overall_success', False)
        success = success_val if isinstance(success_val, bool) else str(success_val).lower() == 'true'
        
        app_state["last_run_status"] = "success" if success else "partial"
        app_state["last_run_result"] = result.get('summary', {})
        
        # Pipeline: Download → Batch Creator → Stock Index
        batch_creator_result = None
        if not request.skip_batch_processor:
            batch_creator_result = await asyncio.to_thread(trigger_batch_creator, trigger_coa=True)
        
        # Build stock index from the consolidated batches
        index_result = await asyncio.to_thread(build_stock_index_from_menus)
        
        return {
            "status": "completed",
            "download_result": result.get('summary', {}),
            "batch_creator_result": batch_creator_result,
            "stock_index_result": index_result
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


@app.post("/build-stock-index")
async def build_stock_index():
    """Manually trigger stock index rebuild from latest menu data."""
    import asyncio
    logger.info("Manual stock index build requested")
    result = await asyncio.to_thread(build_stock_index_from_menus)
    if result.get('success'):
        return result
    else:
        raise HTTPException(status_code=500, detail=result.get('error', 'Failed to build stock index'))


@app.get("/config")
async def get_config():
    """Get current configuration (non-sensitive)."""
    run_mode = os.environ.get("TERPRINT_RUN_MODE", "api-only").lower()
    
    return {
        "run_mode": run_mode,
        "description": "API-only mode" if run_mode == "api-only" else "Scheduler mode with downloads",
        "terprint_config_available": TERPRINT_CONFIG_AVAILABLE,
        "batch_processor_url": BATCH_PROCESSOR_URL,
        "batch_processor_configured": bool(BATCH_PROCESSOR_KEY),
        "strain_index_container": STRAIN_INDEX_CONTAINER,
        "scheduler_running": scheduler.running if run_mode == "scheduler" else False,
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


