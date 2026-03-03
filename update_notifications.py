import re

with open('container_app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the old scheduled_download_job function and replace it
old_pattern = r'async def scheduled_download_job\(\):.*?(?=\n# =+\n# FASTAPI APPLICATION)'

new_function = '''async def scheduled_download_job():
    """Background job for scheduled menu downloads with email notifications."""
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
        # ===== STAGE 1: Menu Download =====
        download_start = time.time()
        notify_stage_start('download', {'trigger': 'scheduled', 'run_number': app_state['scheduled_runs']})
        
        result = run_download()
        success_val = result.get('summary', {}).get('overall_success', False)
        success = success_val if isinstance(success_val, bool) else str(success_val).lower() == 'true'

        app_state["last_run_status"] = "success" if success else "partial"
        app_state["last_run_result"] = result.get('summary', {})
        
        download_duration = time.time() - download_start
        notify_stage_complete('download', success, result.get('summary', {}), download_duration)
        pipeline_results['download_result'] = {'success': success, 'summary': result.get('summary', {})}

        logger.info(f"Scheduled download completed. Success: {success}")

        # ===== STAGE 2: COA Processor =====
        logger.info("Triggering Batch Processor for COA extraction...")
        coa_start = time.time()
        notify_stage_start('coa_process', {'date': datetime.now().strftime('%Y-%m-%d')})
        
        batch_processor_result = {'status': 'skipped'}
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            batch_processor_result = trigger_batch_processor(date=today)
            coa_success = batch_processor_result.get('status') == 'success'
            logger.info(f"Batch Processor result: {batch_processor_result.get('status', 'unknown')}")
        except Exception as batch_err:
            logger.error(f"Batch Processor trigger failed: {str(batch_err)}")
            batch_processor_result = {'status': 'error', 'error': str(batch_err)}
            coa_success = False
        
        coa_duration = time.time() - coa_start
        notify_stage_complete('coa_process', coa_success, batch_processor_result, coa_duration)
        pipeline_results['coa_process_result'] = batch_processor_result

        # ===== STAGE 3: Stock Index Build =====
        logger.info("Building stock index from consolidated batches...")
        index_start = time.time()
        notify_stage_start('stock_index')
        
        index_result = {'success': False, 'error': 'Not attempted'}
        try:
            index_result = build_stock_index_from_menus()
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


'''

# Use regex with DOTALL flag to match across lines
content_new = re.sub(old_pattern, new_function, content, flags=re.DOTALL)

if content_new != content:
    with open('container_app/main.py', 'w', encoding='utf-8') as f:
        f.write(content_new)
    print('Function updated successfully')
else:
    print('Pattern not found or already updated')
