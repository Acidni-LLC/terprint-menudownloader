"""
Terprint Menu Downloader Package

A complete dispensary data collection pipeline with Azure Data Lake integration.

Usage:
    from terprint_menu_downloader import DispensaryOrchestrator
    
    orchestrator = DispensaryOrchestrator()
    results = orchestrator.run_full_pipeline()
"""

__version__ = "1.3.5"

# Import main orchestrator
from .orchestrator import DispensaryOrchestrator

# Import downloaders
from .downloaders import (
    MuvDownloader,
    TrulieveDownloader,
    SunburnDownloader,
    CookiesDownloader,
    FloweryDownloader,
    CuraleafDownloader,
)

# Import storage
from .storage import AzureDataLakeManager

# Import logging utilities
from .logging_config import setup_logging, get_logger

__all__ = [
    "DispensaryOrchestrator",
    "MuvDownloader",
    "TrulieveDownloader", 
    "SunburnDownloader",
    "CookiesDownloader",
    "FloweryDownloader",
    "CuraleafDownloader",
    "AzureDataLakeManager",
    "setup_logging",
    "get_logger",
    "__version__",
]
