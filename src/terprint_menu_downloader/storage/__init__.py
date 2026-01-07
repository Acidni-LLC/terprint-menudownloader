"""
Azure Storage Modules
"""

from .datalake import AzureDataLakeManager
from .azure_config import *

__all__ = [
    'AzureDataLakeManager',
]
