"""
Central Logging Configuration Module for Terprint Applications

This module provides a centralized logging configuration that follows Azure Functions
best practices with support for different log levels, telemetry, and Application Insights.

Usage:
    from logging_config import get_logger, setup_logging
    
    # Basic usage
    logger = get_logger(__name__)
    logger.info("Processing started")
    logger.warning("Potential issue detected")
    logger.error("An error occurred", exc_info=True)
    
    # Custom configuration
    setup_logging(log_level=logging.DEBUG, log_to_file=True, log_dir="custom_logs")
    logger = get_logger(__name__)
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

# Application Insights imports (optional)
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.azure import metrics_exporter
    from applicationinsights import TelemetryClient
    APPLICATION_INSIGHTS_AVAILABLE = True
except ImportError:
    APPLICATION_INSIGHTS_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for console output"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors for console output"""
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Add color to level name
        record.levelname = f"{log_color}{record.levelname}{reset}"
        
        return super().format(record)


class TerprintLogger:
    """
    Centralized logger configuration for Terprint applications.
    Supports file logging, console logging, and Azure Application Insights integration.
    """
    
    _initialized = False
    _loggers = {}
    _telemetry_client = None
    _app_insights_key = None
    _app_insights_handler = None
    
    @staticmethod
    def _callback_add_custom_properties(envelope):
        """Callback to add custom properties to all Application Insights telemetry"""
        envelope.tags['ai.cloud.role'] = 'terprint-python'
        envelope.tags['ai.cloud.roleInstance'] = os.getenv('COMPUTERNAME', 'unknown')
        return True
    
    @classmethod
    def flush_logs(cls):
        """
        Flush all pending logs to Application Insights.
        Should be called at the end of the application to ensure all logs are sent.
        """
        if cls._telemetry_client:
            try:
                cls._telemetry_client.flush()
            except Exception:
                pass
        
        if cls._app_insights_handler:
            try:
                # Force the handler to export pending logs
                if hasattr(cls._app_insights_handler, 'flush'):
                    cls._app_insights_handler.flush()
            except Exception:
                pass
    
    @classmethod
    def setup(
        cls,
        log_level: int = logging.INFO,
        log_to_file: bool = True,
        log_to_console: bool = True,
        log_dir: Optional[str] = None,
        log_filename_prefix: str = "terprint",
        enable_colors: bool = True,
        format_string: Optional[str] = None,
        app_insights_connection_string: Optional[str] = None
    ):
        """
        Configure the logging system for the application.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Enable file logging
            log_to_console: Enable console logging
            log_dir: Directory for log files (default: logs/ in current directory)
            log_filename_prefix: Prefix for log filenames
            enable_colors: Enable colored console output
            format_string: Custom format string for log messages
            app_insights_connection_string: Azure Application Insights connection string
        """
        if cls._initialized:
            return
        
        # Store Application Insights connection string
        if app_insights_connection_string:
            cls._app_insights_key = app_insights_connection_string
        else:
            # Try to get from environment variable
            cls._app_insights_key = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()
        
        # Default format string
        if format_string is None:
            format_string = '%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s'
        
        # Detect Azure Functions environment - disable file logging in read-only environments
        is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
        if is_azure_functions:
            log_to_file = False  # Azure Functions has read-only package directories
        
        # File handler
        if log_to_file:
            if log_dir is None:
                log_dir = os.path.join(os.path.dirname(__file__), "logs")
            
            # Create log directory if it doesn't exist
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            
            # Daily log file
            log_filename = os.path.join(
                log_dir,
                f"{log_filename_prefix}_{datetime.now().strftime('%Y%m%d')}.log"
            )
            
            file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(format_string)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            # Log initialization message
            root_logger.info(f"Logging initialized. Log file: {log_filename}")
        
        # Console handler
        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            
            if enable_colors and sys.stdout.isatty():
                console_formatter = ColoredFormatter(format_string)
            else:
                console_formatter = logging.Formatter(format_string)
            
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # Application Insights handler
        if cls._app_insights_key and APPLICATION_INSIGHTS_AVAILABLE:
            try:
                # Add Azure Log Handler for Application Insights
                # IMPORTANT: Must set logging_sampling_rate=1.0 to capture all logs (not just samples)
                # export_interval: Set to 0.0 for immediate export (no batching)
                cls._app_insights_handler = AzureLogHandler(
                    connection_string=cls._app_insights_key,
                    logging_sampling_rate=1.0,  # Capture 100% of logs
                    export_interval=0.0  # Send logs immediately (no batching/delay)
                )
                # Set the handler level to capture INFO and above
                cls._app_insights_handler.setLevel(logging.INFO)
                
                # Add custom properties to all logs
                cls._app_insights_handler.add_telemetry_processor(cls._callback_add_custom_properties)
                
                root_logger.addHandler(cls._app_insights_handler)
                
                # Initialize telemetry client for custom events
                cls._telemetry_client = TelemetryClient(cls._app_insights_key)
                
                # Enable automatic flushing
                cls._telemetry_client.context.application.ver = '1.0.0'
                cls._telemetry_client.context.device.type = 'Python Script'
                
                root_logger.info("[OK] Application Insights integration enabled")
                
                # Immediate flush to verify connection
                import time
                time.sleep(0.5)  # Brief delay to ensure handler is ready
                cls.flush_logs()
                
            except Exception as e:
                root_logger.warning(f"[!] Could not initialize Application Insights: {e}")
                import traceback
                root_logger.warning(traceback.format_exc())
        elif cls._app_insights_key and not APPLICATION_INSIGHTS_AVAILABLE:
            root_logger.warning("⚠️  Application Insights connection string provided but opencensus packages not installed")
        
        cls._initialized = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name: Logger name (typically __name__ of the calling module)
            
        Returns:
            Logger instance configured with the application settings
        """
        if not cls._initialized:
            cls.setup()
        
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        
        return cls._loggers[name]
    
    @classmethod
    def log_telemetry(
        cls,
        logger: logging.Logger,
        event_name: str,
        properties: Optional[dict] = None,
        measurements: Optional[dict] = None
    ):
        """
        Log custom telemetry event for Application Insights integration.
        
        Args:
            logger: Logger instance
            event_name: Name of the telemetry event
            properties: Dictionary of custom properties
            measurements: Dictionary of custom measurements (numeric values)
        """
        telemetry_data = {
            'event': event_name,
            'properties': properties or {},
            'measurements': measurements or {}
        }
        
        # Log to standard logger
        logger.info(f"TELEMETRY: {telemetry_data}")
        
        # Send to Application Insights if available
        if cls._telemetry_client:
            try:
                cls._telemetry_client.track_event(
                    event_name,
                    properties=properties,
                    measurements=measurements
                )
                cls._telemetry_client.flush()
            except Exception as e:
                logger.debug(f"Failed to send telemetry to Application Insights: {e}")
    
    @classmethod
    def log_exception(
        cls,
        logger: logging.Logger,
        exception: Exception,
        context: Optional[str] = None,
        **kwargs
    ):
        """
        Log an exception with full context and traceback.
        
        Args:
            logger: Logger instance
            exception: Exception object
            context: Additional context about where the exception occurred
            **kwargs: Additional key-value pairs to include in the log
        """
        error_details = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'context': context or 'Unknown',
            **kwargs
        }
        
        logger.error(
            f"Exception occurred: {error_details}",
            exc_info=True,
            extra={'error_details': error_details}
        )
    
    @classmethod
    def log_operation(
        cls,
        logger: logging.Logger,
        operation_name: str,
        status: str,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """
        Log an operation with status and duration for monitoring.
        
        Args:
            logger: Logger instance
            operation_name: Name of the operation
            status: Status of the operation (success, failure, warning)
            duration_ms: Duration in milliseconds
            **kwargs: Additional operation details
        """
        operation_data = {
            'operation': operation_name,
            'status': status,
            'duration_ms': duration_ms,
            **kwargs
        }
        
        if status.lower() == 'success':
            logger.info(f"Operation completed: {operation_data}")
        elif status.lower() == 'failure':
            logger.error(f"Operation failed: {operation_data}")
        else:
            logger.warning(f"Operation warning: {operation_data}")


# Convenience functions for direct import
def setup_logging(**kwargs):
    """Setup logging with custom configuration"""
    TerprintLogger.setup(**kwargs)


def get_logger(name: str = __name__) -> logging.Logger:
    """Get a logger instance for the calling module"""
    return TerprintLogger.get_logger(name)


def log_telemetry(logger: logging.Logger, event_name: str, properties: Optional[dict] = None, measurements: Optional[dict] = None):
    """Log custom telemetry event"""
    TerprintLogger.log_telemetry(logger, event_name, properties, measurements)


def log_exception(logger: logging.Logger, exception: Exception, context: Optional[str] = None, **kwargs):
    """Log an exception with full context"""
    TerprintLogger.log_exception(logger, exception, context, **kwargs)


def log_operation(logger: logging.Logger, operation_name: str, status: str, duration_ms: Optional[float] = None, **kwargs):
    """Log an operation with status and duration"""
    TerprintLogger.log_operation(logger, operation_name, status, duration_ms, **kwargs)


def flush_logs():
    """Flush all pending logs to Application Insights"""
    TerprintLogger.flush_logs()


# Azure Functions specific helpers
class AzureFunctionsLogger:
    """
    Azure Functions specific logging helpers.
    Use when running in Azure Functions context.
    """
    
    @staticmethod
    def setup_with_context(context, log_level: int = logging.INFO):
        """
        Setup logging for Azure Functions with context support.
        
        Args:
            context: Azure Functions context object
            log_level: Logging level
        """
        setup_logging(
            log_level=log_level,
            log_to_file=False,  # Azure Functions handles file logging
            log_to_console=True,
            enable_colors=False  # Azure logs don't support ANSI colors
        )
        
        # Store invocation_id for thread logging
        if hasattr(context, 'invocation_id'):
            logger = get_logger('azure_functions')
            logger.info(f"Function invocation: {context.invocation_id}")
    
    @staticmethod
    def log_from_thread(context, logger: logging.Logger, message: str, level: int = logging.INFO):
        """
        Log from a created thread with proper invocation context.
        
        Args:
            context: Azure Functions context object
            logger: Logger instance
            message: Log message
            level: Log level
        """
        # Set thread local storage for invocation tracking
        if hasattr(context, 'thread_local_storage') and hasattr(context, 'invocation_id'):
            context.thread_local_storage.invocation_id = context.invocation_id
        
        logger.log(level, message)


# Example usage and testing
if __name__ == "__main__":
    # Example 1: Basic usage
    setup_logging(log_level=logging.DEBUG, enable_colors=True)
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    # Example 2: Log operation
    log_operation(logger, "batch_processing", "success", duration_ms=1234.5, batch_count=100)
    
    # Example 3: Log exception
    try:
        raise ValueError("Test exception")
    except Exception as e:
        log_exception(logger, e, context="Example exception handling", batch_id="12345")
    
    # Example 4: Log telemetry
    log_telemetry(
        logger,
        "batch_processed",
        properties={"dispensary": "Trulieve", "format": "ACS"},
        measurements={"processing_time_ms": 500, "record_count": 25}
    )
    
    print("\n[OK] Logging examples completed. Check the logs/ directory for output.")
