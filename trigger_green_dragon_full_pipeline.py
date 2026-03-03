#!/usr/bin/env python3
"""
Green Dragon Full Pipeline Trigger

Executes:
1. Stage 2: Menu Downloader (Green Dragon)
2. Stage 2.5: Batch Creator (consolidates downloads)
3. Stage 3: Batch Processor (COA extraction)

Safety: Aborts if total_products == 0
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import requests

from terprint_menu_downloader.orchestrator import DispensaryOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


async def trigger_green_dragon_pipeline():
    """Execute full Green Dragon pipeline with safety checks."""
    
    logger.info("=" * 80)
    logger.info("GREEN DRAGON FULL PIPELINE TRIGGER")
    logger.info("=" * 80)
    
    # Initialize orchestrator
    logger.info("")
    logger.info("Initializing DispensaryOrchestrator...")
    orchestrator = DispensaryOrchestrator()
    
    logger.info("")
    logger.info("STAGE 2: Menu Downloader - Green Dragon")
    logger.info("-" * 80)
    
    # Get Green Dragon downloader
    if "green_dragon" not in orchestrator.downloaders:
        logger.error("ERROR: Green Dragon downloader not found in orchestrator!")
        return False
    
    green_dragon_entry = orchestrator.downloaders["green_dragon"]
    green_dragon_dl = green_dragon_entry["downloader"]
    logger.info(f"Green Dragon downloader found")
    logger.info(f"   Stores to download: {len(green_dragon_dl.stores)}")
    logger.info(f"   Total batches: {green_dragon_dl.total_batches}")
    logger.info(f"   Parallel downloads: {green_dragon_dl.parallel_stores}")
    
    logger.info("")
    logger.info("Starting download...")
    result = green_dragon_dl.download()
    
    # result is a list of tuples: [(store_slug, data_dict), ...]
    logger.info(f"Download completed!")
    logger.info(f"   Results returned: {len(result)} store(s)")
    
    total_products = sum(store_data.get('product_count', 0) for _, store_data in result)
    logger.info(f"   Total products across all stores: {total_products}")
    
    if total_products == 0:
        logger.error("ERROR: No products downloaded! Green Dragon may not be working.")
        logger.error(f"   Result: {result}")
        return False
    
    # Step 2: Trigger batch creator
    logger.info("")
    logger.info("STAGE 2.5: Batch Creator")
    logger.info("-" * 80)
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        batch_creator_url = "https://ca-terprint-batches.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/trigger"
        
        logger.info(f"Calling: {batch_creator_url}")
        logger.info(f"Payload: date={today}")
        
        response = requests.post(
            batch_creator_url,
            json={"date": today},
            timeout=120
        )
        
        logger.info(f"Response: HTTP {response.status_code}")
        if response.text:
            logger.info(f"Response body: {response.text[:200]}")
        
        if response.status_code in [200, 202, 204]:
            logger.info("Successfully triggered batch creator")
        else:
            logger.warning(f"Batch creator may have issues (HTTP {response.status_code})")
            
    except requests.exceptions.Timeout:
        logger.warning("Batch creator request timed out (expected for long operations)")
    except Exception as e:
        logger.warning(f"Could not reach batch creator: {e}")
    
    # Step 3: Trigger batch processor (COA)
    logger.info("")
    logger.info("STAGE 3: Batch Processor (COA Processing)")
    logger.info("-" * 80)
    
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        batch_processor_url = "https://ca-terprint-batchprocessor.kindmoss-c6723cbe.eastus2.azurecontainerapps.io/api/run-batch-processor"
        
        logger.info(f"Calling: {batch_processor_url}")
        logger.info(f"Payload: date={today}")
        
        response = requests.post(
            batch_processor_url,
            json={"date": today},
            timeout=180
        )
        
        logger.info(f"Response: HTTP {response.status_code}")
        if response.text:
            logger.info(f"Response body: {response.text[:200]}")
        
        if response.status_code in [200, 202, 204]:
            logger.info("Successfully triggered batch processor")
            logger.info("COA extraction will begin processing")
        else:
            logger.warning(f"Batch processor may have issues (HTTP {response.status_code})")
            
    except requests.exceptions.Timeout:
        logger.warning("Batch processor request timed out (expected for long operations)")
    except Exception as e:
        logger.warning(f"Could not reach batch processor: {e}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("PIPELINE EXECUTION COMPLETE")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Next Steps:")
    logger.info("1. Data will be available in blob storage: jsonfiles/dispensaries/green-dragon/")
    logger.info("2. Batch file will be created: jsonfiles/batches/consolidated_batches_YYYYMMDD.json")
    logger.info("3. COA data will be extracted to SQL tables: Products, ProductCannabinoids, ProductEffects")
    logger.info("4. Access via API: GET /menus?dispensary=green_dragon")
    logger.info("")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(trigger_green_dragon_pipeline())
        if success:
            logger.info("✅ Pipeline triggered successfully")
            sys.exit(0)
        else:
            logger.error("Pipeline trigger failed")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
