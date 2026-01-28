# notifications.py - Email notifications for pipeline stages
"""
Email notifications using Azure Communication Services.
Sends notifications at pipeline stage boundaries.
"""
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Notification configuration
# Default recipient from terprint/product.yaml team.owner
NOTIFICATION_ENABLED = os.environ.get('NOTIFICATION_ENABLED', 'true').lower() == 'true'
NOTIFICATION_RECIPIENT = os.environ.get('NOTIFICATION_RECIPIENT', 'jamieson@acidni.net')

# Pipeline stages for context
PIPELINE_STAGES = {
    'download': {'name': 'Menu Download', 'emoji': '📥', 'order': 1},
    'batch_create': {'name': 'Batch Creator', 'emoji': '📦', 'order': 2},
    'coa_process': {'name': 'COA Processor', 'emoji': '🔬', 'order': 3},
    'stock_index': {'name': 'Stock Index Build', 'emoji': '📊', 'order': 4},
}


def send_email(subject: str, body: str, recipient: Optional[str] = None) -> bool:
    """
    Send email using Azure Communication Services.
    
    Args:
        subject: Email subject line
        body: Email body (plain text or HTML)
        recipient: Override default recipient
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not NOTIFICATION_ENABLED:
        logger.debug("Email notifications disabled")
        return True
    
    to_address = recipient or NOTIFICATION_RECIPIENT
    if not to_address:
        logger.warning("No notification recipient configured, skipping email")
        return False
    
    try:
        from azure.communication.email import EmailClient
        
        # Get connection string from environment (injected from Key Vault)
        acs_connection_string = os.environ.get('ACS_CONNECTION_STRING')
        sender_email = os.environ.get('ACS_SENDER_EMAIL', 'DoNotReply@acidni.net')
        
        if not acs_connection_string:
            logger.warning("ACS_CONNECTION_STRING not configured, skipping email")
            return False
        
        # Create email client
        client = EmailClient.from_connection_string(acs_connection_string)
        
        # Prepare email message
        message = {
            "senderAddress": sender_email,
            "recipients": {
                "to": [{"address": to_address}]
            },
            "content": {
                "subject": subject,
                "plainText": body,
                "html": f"<html><body><pre style='font-family: monospace;'>{body}</pre></body></html>"
            }
        }
        
        # Send email
        poller = client.begin_send(message)
        result = poller.result()
        
        logger.info(f"Email sent successfully: {subject} -> {to_address}")
        return True
        
    except ImportError:
        logger.warning("azure-communication-email package not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def notify_stage_start(stage: str, context: Optional[dict] = None) -> bool:
    """
    Send notification when a pipeline stage starts.
    
    Args:
        stage: Stage key from PIPELINE_STAGES
        context: Additional context to include in the email
    """
    stage_info = PIPELINE_STAGES.get(stage, {'name': stage, 'emoji': '▶️', 'order': 0})
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    subject = f"{stage_info['emoji']} Terprint Pipeline: {stage_info['name']} Started"
    
    body = f"""Terprint Data Pipeline - Stage Started
=====================================

Stage: {stage_info['name']} ({stage_info['order']}/4)
Time:  {timestamp}
Status: 🔄 In Progress

"""
    if context:
        body += "Context:\n"
        for key, value in context.items():
            body += f"  - {key}: {value}\n"
    
    body += """
---
This is an automated notification from Terprint Menu Downloader.
"""
    
    return send_email(subject, body)


def notify_stage_complete(stage: str, success: bool, result: Optional[dict] = None, duration_seconds: Optional[float] = None) -> bool:
    """
    Send notification when a pipeline stage completes.
    
    Args:
        stage: Stage key from PIPELINE_STAGES
        success: Whether the stage completed successfully
        result: Stage result data to include
        duration_seconds: How long the stage took
    """
    stage_info = PIPELINE_STAGES.get(stage, {'name': stage, 'emoji': '✅', 'order': 0})
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    status_emoji = '✅' if success else '❌'
    status_text = 'Completed Successfully' if success else 'Failed'
    
    subject = f"{status_emoji} Terprint Pipeline: {stage_info['name']} {status_text}"
    
    body = f"""Terprint Data Pipeline - Stage Completed
========================================

Stage:    {stage_info['name']} ({stage_info['order']}/4)
Time:     {timestamp}
Status:   {status_emoji} {status_text}
"""
    
    if duration_seconds:
        body += f"Duration: {duration_seconds:.1f} seconds\n"
    
    if result:
        body += "\nResults:\n"
        for key, value in result.items():
            if isinstance(value, dict):
                body += f"  {key}:\n"
                for k, v in value.items():
                    body += f"    - {k}: {v}\n"
            else:
                body += f"  - {key}: {value}\n"
    
    body += """
---
This is an automated notification from Terprint Menu Downloader.
"""
    
    return send_email(subject, body)


def notify_pipeline_summary(results: dict) -> bool:
    """
    Send summary notification after full pipeline run.
    
    Args:
        results: Full pipeline results including all stages
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Determine overall status
    overall_success = results.get('summary', {}).get('overall_success', False)
    status_emoji = '✅' if overall_success else '⚠️'
    status_text = 'Completed' if overall_success else 'Completed with Issues'
    
    subject = f"{status_emoji} Terprint Pipeline: Full Run {status_text}"
    
    body = f"""Terprint Data Pipeline - Full Run Summary
==========================================

Time:    {timestamp}
Status:  {status_emoji} {status_text}

Stage Summary:
"""
    
    # Add stage results
    stages = ['download', 'batch_create', 'coa_process', 'stock_index']
    for stage_key in stages:
        stage_info = PIPELINE_STAGES.get(stage_key, {})
        stage_result = results.get(f'{stage_key}_result', {})
        stage_success = stage_result.get('success', stage_result.get('status') == 'success')
        stage_emoji = '✅' if stage_success else '❌'
        body += f"  {stage_info.get('emoji', '•')} {stage_info.get('name', stage_key)}: {stage_emoji}\n"
    
    # Download summary if available
    summary = results.get('summary', {})
    if summary:
        body += "\nDownload Details:\n"
        for key in ['dispensaries_processed', 'total_files_uploaded', 'total_menus', 'total_items']:
            if key in summary:
                body += f"  - {key.replace('_', ' ').title()}: {summary[key]}\n"
    
    body += """
---
This is an automated notification from Terprint Menu Downloader.
Next scheduled run: Check Container App logs for schedule.
"""
    
    return send_email(subject, body)
