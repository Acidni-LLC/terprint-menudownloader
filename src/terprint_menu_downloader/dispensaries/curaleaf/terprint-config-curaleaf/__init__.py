"""
Curaleaf Florida Configuration for terprint-config package.

This module provides the dispensary configuration for Curaleaf FL stores
to be integrated into the Menu Downloader pipeline.

Usage:
    from terprint_config.dispensaries.curaleaf import CURALEAF_CONFIG, get_fl_stores
"""

from .config import CURALEAF_CONFIG, get_fl_stores, FL_STORES

__all__ = ['CURALEAF_CONFIG', 'get_fl_stores', 'FL_STORES']
__version__ = '1.0.0'
