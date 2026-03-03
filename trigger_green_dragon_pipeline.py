#!/usr/bin/env python3
"""Direct trigger of Green Dragon menu download, batch creation, and COA processing"""

import asyncio
import logging
from datetime import datetime
from terprint_menu_downloader import DispensaryOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def trigger_green_dragon_pipeline():
    """Trigger Green Dragon download → batch → processing"""
    
    logger.info("=" * 80)
    logger.info("🟢 GREEN DRAGON PIPELINE TRIGGER")
    logger.info("=" * 80)
    
    try:
        # Initialize orchestrator
        logger.info("Initializing DispensaryOrchestrator...")
        orchestrator = DispensaryOrchestrator(in_memory=False)
        
        # Step 1: Download Green Dragon only
        logger.info("")
        logger.info("📥 STAGE 2: Menu Downloader - Green Dragon")
        logger.info("-" * 80)
        
        if 'green_dragon' not in orchestrator.downloaders:
            logger.error("❌ Green Dragon downloader not found in orchestrator!")
            logger.error(f"   Available downloaders: {list(orchestrator.downloaders.keys())}")
            return False
        
        green_dragon_dl = orchestrator.downloaders['green_dragon']['downloader']
        logger.info(f"✅ Green Dragon downloader found")
        logger.info(f"   Stores to download: {green_dragon_dl.store_count}")
        logger.info(f"   Total batches: {green_dragon_dl.total_batches}")
        logger.info(f"   Parallel downloads: {green_dragon_dl.parallel_stores}")
        
        logger.info("")
        logger.info("Starting download...")
        result = green_dragon_dl.download()
        
        # result is a list of tuples: [(store_slug, data_dict), ...]
        logger.info(f"✅ Download completed!")
        logger.info(f"   Results returned: {len(result)} store(s)")
        
        total_products = sum(store_data.get('product_count', 0) for _, store_data in result)
        logger.info(f"   Total products across all stores: {total_products}")
        
        if total_products == 0:
            logger.error("❌ No products downloaded! Green Dragon may not be working.")
            logger.error(f"   Result: {result}")
            return False
        
        # Step 2: Trigger batch creator
        logger.info("")
        logger.info("📦 STAGE 2.5: Batch Creator")
        logger.info("-" * 80)
        logger.info("Triggering batch consolidation...")
        
        batch_result = await orchestrator.trigger_batch_creator_async()
        logger.info(f"✅ Batch creation triggered!")
        logger.info(f"   Batch date: {datetime.now().strftime('%Y%m%d')}")
        logger.info(f"   Status: {batch_result.get('status', 'unknown')}")
        
        # Step 3: Trigger batch processor (COA extraction)
        logger.info("")
        logger.info("🔧 STAGE 3: Batch Processor - COA Extraction")
        logger.info("-" * 80)
        logger.info("Triggering COA processing...")
        
        processor_result = await orchestrator.trigger_batch_processor_async()
        logger.info(f"✅ Batch processor triggered!")
        logger.info(f"   Status: {processor_result.get('status', 'unknown')}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ GREEN DRAGON PIPELINE COMPLETE")
        logger.info("=" * 80)
        logger.info("Data will be available via APIM /menus?dispensary=green_dragon shortly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    success = asyncio.run(trigger_green_dragon_pipeline())
    exit(0 if success else 1)
