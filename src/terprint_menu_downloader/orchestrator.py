"""
Dispensary Data Orchestrator
Automatically downloads data from multiple dispensaries and uploads to Azure Event House

When used as a package, imports come from the terprint_menu_downloader package structure.
When used standalone (python menu_downloader.py), it uses sys.path manipulation for backwards compatibility.
"""
import os
import sys
import json
import csv
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Detect if running as a package or standalone
_RUNNING_AS_PACKAGE = __name__ != "__main__" and "terprint_menu_downloader" in __name__

# Get current directory for path calculations  
current_dir = os.path.dirname(os.path.abspath(__file__))

if _RUNNING_AS_PACKAGE:
    # Running as installed package - use relative imports
    # current_dir IS the terprint_menu_downloader folder (where orchestrator.py lives)
    package_dir = current_dir  # terprint_menu_downloader folder
    docs_dir = os.path.join(package_dir, 'menus')  # menus subpackage
    terprint_python_dir = package_dir  # for backwards compat references
else:
    # Running standalone - set up paths for backwards compatibility
    parent_dir = os.path.dirname(current_dir)
    terprint_python_dir = os.path.join(parent_dir, "Terprint.Python")
    sys.path.extend([
        current_dir, 
        parent_dir, 
        terprint_python_dir,
        os.path.join(terprint_python_dir, "menus"),
        os.path.join(terprint_python_dir, "menus", "trulieve"),
    ])
    
    # Allow using local `docs/` copies if the sibling Terprint.Python repo is not available.
    docs_dir = os.path.join(current_dir, 'docs')
    if os.path.exists(docs_dir):
        sys.path.insert(0, docs_dir)
        sys.path.insert(0, os.path.join(docs_dir, 'menus'))
        sys.path.insert(0, os.path.join(docs_dir, 'menus', 'trulieve'))

# Load environment variables from .env file
from dotenv import load_dotenv
if _RUNNING_AS_PACKAGE:
    # When running as package, look for .env in current working directory
    load_dotenv()
else:
    env_path = os.path.join(terprint_python_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        env_path = os.path.join(parent_dir, '.env')
        load_dotenv(env_path)

# Import centralized logging
if _RUNNING_AS_PACKAGE:
    from .logging_config import setup_logging, get_logger, log_operation, log_exception, log_telemetry, flush_logs
else:
    try:
        sys.path.insert(0, os.path.join(parent_dir, "Terprint.Python.Logger"))
        from logging_config import setup_logging, get_logger, log_operation, log_exception, log_telemetry, flush_logs
    except ImportError:
        from logging_config import setup_logging, get_logger, log_operation, log_exception, log_telemetry, flush_logs

# Import job tracker for restart capability
if _RUNNING_AS_PACKAGE:
    try:
        from .job_tracker import JobTracker, JobStatus, StoreStatus
        JOB_TRACKING_AVAILABLE = True
    except ImportError:
        JOB_TRACKING_AVAILABLE = False
else:
    try:
        from job_tracker import JobTracker, JobStatus, StoreStatus
        JOB_TRACKING_AVAILABLE = True
    except ImportError:
        JOB_TRACKING_AVAILABLE = False

# Set up centralized logging - deferred until needed
import logging
_logging_initialized = False

def _initialize_logging():
    """Initialize logging - call this before any logging operations."""
    global _logging_initialized
    if _logging_initialized:
        return
    
    # Detect Azure Functions environment and use appropriate log directory
    is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
    
    if is_azure_functions:
        # In Azure Functions, use /tmp which is writable, or disable file logging
        log_dir = '/tmp/terprint_logs'
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            # If we can't create log dir, disable file logging
            log_dir = None
    else:
        log_dir = None  # Use default (next to module)
    
    if log_dir:
        setup_logging(
            log_level=logging.INFO,
            log_filename_prefix="dispensary_orchestrator",
            log_dir=log_dir,
            app_insights_connection_string=os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        )
    else:
        # For Azure Functions without file logging, just set up console + App Insights
        setup_logging(
            log_level=logging.INFO,
            log_filename_prefix="dispensary_orchestrator",
            log_to_file=False,
            app_insights_connection_string=os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
        )
    
    # Suppress verbose Azure SDK logging (Request/Response headers)
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure').setLevel(logging.WARNING)
    
    _logging_initialized = True

# Get logger for this module (does not require logging to be initialized)
logger = get_logger(__name__)

# Import Azure configuration
if _RUNNING_AS_PACKAGE:
    from .storage.azure_config import *
else:
    try:
        sys.path.insert(0, os.path.join(parent_dir, "Terprint.Python.Storage"))
        from azure_config import *
    except ImportError:
        sys.path.insert(0, os.path.join(terprint_python_dir, "menumover"))
        from azure_config import *

# Import Azure Data Lake Manager
if _RUNNING_AS_PACKAGE:
    try:
        from .storage.datalake import AzureDataLakeManager
        from azure.identity import ClientSecretCredential
        AZURE_DATALAKE_AVAILABLE = True
        logger.info("Azure Data Lake Manager imported successfully")
    except ImportError as e:
        logger.warning(f"Could not import Azure Data Lake Manager: {e}")
        AZURE_DATALAKE_AVAILABLE = False
else:
    try:
        try:
            from saveJsonToAzureDataLake import AzureDataLakeManager
        except ImportError:
            sys.path.insert(0, os.path.join(terprint_python_dir, "azureDataLake"))
            from saveJsonToAzureDataLake import AzureDataLakeManager
        from azure.identity import ClientSecretCredential
        AZURE_DATALAKE_AVAILABLE = True
        logger.info("Azure Data Lake Manager imported successfully")
    except ImportError as e:
        logger.warning(f"Could not import Azure Data Lake Manager: {e}")
        AZURE_DATALAKE_AVAILABLE = False

# Import download modules
if _RUNNING_AS_PACKAGE:
    try:
        from .downloaders import MuvDownloader, TrulieveDownloader, SunburnDownloader, CookiesDownloader, FloweryDownloader, CuraleafDownloader, GreenDragonDownloader
        MODULAR_DOWNLOADERS_AVAILABLE = True
        logger.info("Modular downloaders imported successfully")
    except ImportError as e:
        logger.warning(f"Could not import modular downloaders: {e}")
        MODULAR_DOWNLOADERS_AVAILABLE = False
else:
    try:
        sys.path.insert(0, os.path.join(parent_dir, "Terprint.Python.COADataExtractor"))
        from downloads import MuvDownloader, TrulieveDownloader, SunburnDownloader, CookiesDownloader, FloweryDownloader, CuraleafDownloader, GreenDragonDownloader
        MODULAR_DOWNLOADERS_AVAILABLE = True
        logger.info("Modular downloaders imported successfully")
    except ImportError as e:
        # Fallback to old location if new location not available
        try:
            sys.path.insert(0, os.path.join(terprint_python_dir, "menumover", "downloads"))
            from downloads import MuvDownloader, TrulieveDownloader, SunburnDownloader, CookiesDownloader, FloweryDownloader, CuraleafDownloader, GreenDragonDownloader
            MODULAR_DOWNLOADERS_AVAILABLE = True
            logger.info("Modular downloaders imported from fallback location")
        except ImportError as e2:
            logger.warning(f"Could not import modular downloaders: {e2}")
            MODULAR_DOWNLOADERS_AVAILABLE = False


class DispensaryOrchestrator:
    """Main orchestrator for dispensary data collection and upload"""
    
    def __init__(
        self, 
        output_dir: Optional[str] = None, 
        dev_mode: bool = False, 
        in_memory: bool = True,
        curaleaf_batch: Optional[int] = None,
        curaleaf_stores_per_batch: int = 15,
        curaleaf_parallel_stores: int = 3
    ):
        """Initialize the orchestrator.
        
        Args:
            output_dir: Directory for local file output (optional)
            dev_mode: Enable development mode with reduced data
            in_memory: Operate in-memory without local file writes
            curaleaf_batch: Specific Curaleaf batch to download (0-3), None for all
            curaleaf_stores_per_batch: Number of stores per Curaleaf batch (default 15)
            curaleaf_parallel_stores: Number of parallel Curaleaf downloads (default 3)
        """
        # Initialize logging on first instantiation
        _initialize_logging()
        
        # Curaleaf batching configuration
        self.curaleaf_batch = curaleaf_batch
        self.curaleaf_stores_per_batch = curaleaf_stores_per_batch
        self.curaleaf_parallel_stores = curaleaf_parallel_stores
        
        # Default: operate in-memory (do not write combined artifacts to disk)
        self.in_memory = in_memory
        # If running fully in-memory, avoid local downloads directory
        if self.in_memory:
            self.output_dir = None
        else:
            self.output_dir = output_dir or os.path.join(current_dir, "downloads")
        self.dev_mode = dev_mode
        # Note: output_dir is kept for backward compatibility but files will be saved to Azure Data Lake
        
        # Results tracking
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'downloads': {},
            'uploads': {},
            'errors': [],
            'summary': {}
        }
        
        # Batch tracking - in-memory collection during downloads
        self.batch_tracker = []
        self.batch_counter = 0
        
        # Initialize job tracker for restart capability
        self.job_tracker = None
        self.current_job_id = None
        if JOB_TRACKING_AVAILABLE:
            try:
                self.job_tracker = JobTracker(application_name="MenuDownloader")
                logger.info("[OK] Job tracker initialized - restart capability enabled")
            except Exception as e:
                logger.warning(f"Could not initialize job tracker: {e}")
                self.job_tracker = None
        
        # Initialize Azure Data Lake Manager
        self.azure_manager = None
        if AZURE_DATALAKE_AVAILABLE:
            try:
                # In Azure Functions, USE_AZURE_CLI is checked but we should try Managed Identity first
                is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
                
                # Try Managed Identity (DefaultAzureCredential) first in Azure Functions
                # This covers: Managed Identity, Azure CLI, Visual Studio, etc.
                if is_azure_functions or USE_AZURE_CLI:
                    credential = None  # Will use DefaultAzureCredential in AzureDataLakeManager
                else:
                    # Use service principal credentials
                    credential = ClientSecretCredential(
                        tenant_id=AZURE_TENANT_ID,
                        client_id=AZURE_CLIENT_ID,
                        client_secret=AZURE_CLIENT_SECRET
                    )
                
                logger.info(f"[INIT] Creating Azure Data Lake Manager...")
                logger.info(f"[INIT]   Account: {AZURE_STORAGE_ACCOUNT_NAME}")
                logger.info(f"[INIT]   Container: {AZURE_CONTAINER_NAME}")
                logger.info(f"[INIT]   Auth Method: {'Managed Identity/DefaultAzureCredential' if credential is None else 'Service Principal'}")
                
                self.azure_manager = AzureDataLakeManager(
                    account_name=AZURE_STORAGE_ACCOUNT_NAME,
                    container_name=AZURE_CONTAINER_NAME,
                    credential=credential
                )
                
                logger.info(f"[OK] Azure Data Lake Manager initialized: {AZURE_STORAGE_ACCOUNT_NAME}/{AZURE_CONTAINER_NAME}")
                
                # Test connection
                container_info = self.azure_manager.get_container_info()
                if container_info:
                    logger.info(f"[OK] Connected to Azure Data Lake successfully")
                else:
                    logger.warning("[!] Could not verify Azure Data Lake connection")
                    
            except Exception as e:
                log_exception(
                    logger,
                    e,
                    context="Azure Data Lake Manager initialization",
                    account_name=AZURE_STORAGE_ACCOUNT_NAME,
                    container_name=AZURE_CONTAINER_NAME
                )
                logger.critical(f"[CRITICAL] Azure Data Lake Manager initialization FAILED!")
                logger.critical(f"[CRITICAL] Check that Azure credentials are properly set:")
                logger.critical(f"[CRITICAL]   - AZURE_TENANT_ID: {'SET' if os.environ.get('AZURE_TENANT_ID') else 'MISSING'}")
                logger.critical(f"[CRITICAL]   - AZURE_CLIENT_ID: {'SET' if os.environ.get('AZURE_CLIENT_ID') else 'MISSING'}")
                logger.critical(f"[CRITICAL]   - AZURE_CLIENT_SECRET: {'SET' if os.environ.get('AZURE_CLIENT_SECRET') else 'MISSING'}")
                logger.critical(f"[CRITICAL]   - AZURE_STORAGE_ACCOUNT_NAME: {AZURE_STORAGE_ACCOUNT_NAME}")
                logger.critical(f"[CRITICAL]   - AZURE_CONTAINER_NAME: {AZURE_CONTAINER_NAME}")
                logger.critical(f"[CRITICAL] Error: {e}")
                logger.critical("Will proceed WITHOUT Azure uploads - BATCH FILES WILL NOT BE SAVED!")
                self.azure_manager = None
        else:
            logger.critical("[CRITICAL] Azure Data Lake Manager not available! Check if saveJsonToAzureDataLake.py is properly installed.")
            logger.critical("[CRITICAL] BATCH FILES WILL NOT BE SAVED!")

        
        # Initialize downloaders - ONLY use modular downloaders, no fallbacks
        try:
            self.downloaders = self._init_downloaders()
        except Exception as e:
            log_exception(logger, e, context="Downloader initialization")
            self.downloaders = {}

        # Genetics extraction configuration (package mode only)
        self._genetics_scraper = None
        self._genetics_storage = None
        self.enable_genetics = os.environ.get("ENABLE_GENETICS", "1") != "0"
        self.save_genetics = os.environ.get("SAVE_GENETICS", "1") != "0"
        if _RUNNING_AS_PACKAGE and self.enable_genetics:
            try:
                from .genetics.scraper import GeneticsScraper
                from .genetics.storage import GeneticsStorage
                self._genetics_scraper = GeneticsScraper()
                self._genetics_storage = GeneticsStorage()
                logger.info(f"[GENETICS] Enabled: {self.enable_genetics}, Save: {self.save_genetics}")
            except Exception as e:
                logger.warning(f"[GENETICS] Genetics modules not available: {e}")
                self._genetics_scraper = None
                self._genetics_storage = None
                self.enable_genetics = False
                self.save_genetics = False

    def find_all_muv_json_files(self):
        """List all muv*.json files from Azure Data Lake"""
        if not self.azure_manager:
            logger.warning("Azure Data Lake Manager not initialized")
            return []
        
        try:
            muv_files = []
            # List files from Azure Data Lake in muv directory
            all_files = self.azure_manager.list_files("dispensaries/muv")
            muv_files = [f for f in all_files if 'muv' in f.lower() and f.endswith('.json')]
            return muv_files
        except Exception as e:
            logger.error(f"Error listing muv files from Azure: {e}")
            return []
    
    def _init_downloaders(self) -> Dict:
        """Initialize dispensary downloaders - MODULAR ONLY"""
        downloaders = {}
        
        if not MODULAR_DOWNLOADERS_AVAILABLE:
            logger.error("Modular downloaders not available! Check downloads/ directory and imports.")
            return {}
        
        try:
            # MUV Downloader - Using all known store IDs
            # Based on MUV's 86 Florida locations
            muv_store_ids = [
                '298', '299', '300', '301', '302', '303', '304', '305', '306', '307',
                '308', '309', '310', '311', '312', '313', '314', '315', '316', '317',
                '318', '319', '320', '321', '322', '323', '324', '325', '326', '327',
                '328', '329', '330', '331', '332', '333', '334', '335', '336', '337',
                '338', '339', '340', '341', '342', '343', '344', '345', '346', '347',
                '348', '349', '350', '351', '352', '353', '354', '355', '356', '357',
                '358', '359', '360', '361', '362', '363', '364', '365', '366', '367',
                '368', '369', '370', '371', '372', '373', '374', '375', '376', '377',
                '378', '379', '380', '381', '382', '383'
            ]
            
            logger.info("Initializing MUV downloader...")
            logger.info(f"MUV: Configured to download from {len(muv_store_ids)} stores")
            downloaders['muv'] = {
                'name': 'MUV',
                'enabled': True,
                'downloader': MuvDownloader(
                    output_dir=self.output_dir,
                    store_ids=muv_store_ids,
                    azure_manager=self.azure_manager
                )
            }
            # Signal downloader whether it should write local files
            try:
                dl = downloaders['muv']['downloader']
                setattr(dl, 'write_local', not self.in_memory)
            except Exception:
                pass
            
            # Trulieve Downloader  
            logger.info("Initializing Trulieve downloader...")
            
            # Load Trulieve stores from local menus/storeid_location_list.csv (172 stores)
            # and category IDs from menus/menu_config.json
            trulieve_store_ids = None
            trulieve_category_ids = ["MjA4", "MjM3", "MjA5", "Ng=="]  # Whole Flower (208), Vape Carts (237), Vaporizers (209), Concentrates (6)
            
            # Path to the menus folder (sibling to orchestrator.py)
            menus_dir = os.path.join(os.path.dirname(__file__), "menus")
            csv_path = os.path.join(menus_dir, "storeid_location_list.csv")
            
            logger.info(f"Trulieve: Loading stores from {csv_path}")
            
            if os.path.exists(csv_path):
                try:
                    with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:  # utf-8-sig handles BOM
                        reader = csv.DictReader(csvfile)
                        trulieve_store_ids = [row.get('location', '').strip() for row in reader if row.get('location', '').strip()]
                    logger.info(f"Trulieve: Loaded {len(trulieve_store_ids)} store IDs from {csv_path}")
                    logger.info(f"Trulieve: Using {len(trulieve_category_ids)} category IDs")
                except Exception as e:
                    logger.error(f"Trulieve: Error reading CSV: {e}")
            else:
                logger.error(f"Trulieve: Store file not found at {csv_path}")
                logger.error(f"Trulieve: Contents of {os.path.dirname(__file__)}: {os.listdir(os.path.dirname(__file__))}")
            
            downloaders['trulieve'] = {
                'name': 'Trulieve',
                'enabled': True,
                'downloader': TrulieveDownloader(
                    output_dir=self.output_dir,
                    dev_mode=self.dev_mode,
                    store_ids=trulieve_store_ids if not self.dev_mode else None,
                    category_ids=trulieve_category_ids if not self.dev_mode else None,
                    azure_manager=self.azure_manager
                )
            }
            try:
                dl = downloaders['trulieve']['downloader']
                setattr(dl, 'write_local', not self.in_memory)
            except Exception:
                pass
            
            # Sunburn Downloader
            logger.info("Initializing Sunburn downloader...")
            downloaders['sunburn'] = {
                'name': 'Sunburn',
                'enabled': False,  # Disabled due to anti-bot protection
                'downloader': SunburnDownloader(
                    output_dir=self.output_dir,
                    azure_manager=self.azure_manager
                )
            }
            try:
                dl = downloaders['sunburn']['downloader']
                setattr(dl, 'write_local', not self.in_memory)
            except Exception:
                pass
            
            # Cookies Florida Downloader
            logger.info("Initializing Cookies Florida downloader...")
            downloaders['cookies'] = {
                'name': 'Cookies Florida',
                'enabled': True,
                'downloader': CookiesDownloader(
                    output_dir=self.output_dir,
                    azure_manager=self.azure_manager
                )
            }
            logger.info(f"Cookies: Configured to download from {len(downloaders['cookies']['downloader'].location_slugs)} locations")
            try:
                dl = downloaders['cookies']['downloader']
                setattr(dl, 'write_local', not self.in_memory)
            except Exception:
                pass
            
            # The Flowery Downloader
            logger.info("Initializing The Flowery downloader...")
            
            # Load Flowery store IDs from CSV
            flowery_store_ids = []
            flowery_csv_path = os.path.join(os.path.dirname(__file__), "flowery_stores.csv")
            if os.path.exists(flowery_csv_path):
                try:
                    with open(flowery_csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            location_id = row.get('location_id', row.get('id', '')).strip()
                            if location_id:
                                flowery_store_ids.append(location_id)
                    logger.info(f"Flowery: Loaded {len(flowery_store_ids)} store IDs from CSV: {flowery_csv_path}")
                except Exception as e:
                    logger.warning(f"Flowery: Could not load store IDs from CSV: {e}")
            
            downloaders['flowery'] = {
                'name': 'The Flowery',
                'enabled': True,
                'downloader': FloweryDownloader(
                    output_dir=self.output_dir,
                    azure_manager=self.azure_manager,
                    location_ids=flowery_store_ids if flowery_store_ids else None
                ),
                'store_ids': flowery_store_ids if flowery_store_ids else ['dynamic']
            }
            
            store_count_msg = f"{len(flowery_store_ids)} stores" if flowery_store_ids else "all Florida locations (dynamic)"
            logger.info(f"Flowery: Configured to download from {store_count_msg}")
            try:
                dl = downloaders['flowery']['downloader']
                setattr(dl, 'write_local', not self.in_memory)
            except Exception:
                pass
            
            # Curaleaf Florida Downloader (HTML scraping via SweedPOS)
            logger.info("Initializing Curaleaf downloader...")
            try:
                curaleaf_downloader = CuraleafDownloader(
                    output_dir=self.output_dir,
                    azure_manager=self.azure_manager,
                    store_batch=self.curaleaf_batch,
                    stores_per_batch=self.curaleaf_stores_per_batch,
                    parallel_stores=self.curaleaf_parallel_stores
                )
                downloaders['curaleaf'] = {
                    'name': 'Curaleaf',
                    'enabled': True,
                    'downloader': curaleaf_downloader
                }
                batch_info = f" (batch {self.curaleaf_batch})" if self.curaleaf_batch is not None else " (all stores)"
                logger.info(f"Curaleaf: Configured to download {curaleaf_downloader.store_count} stores{batch_info}")
                logger.info(f"Curaleaf: {curaleaf_downloader.total_batches} total batches, {curaleaf_downloader.parallel_stores} parallel downloads")
                try:
                    setattr(curaleaf_downloader, 'write_local', not self.in_memory)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Curaleaf: Could not initialize downloader: {e}")
            
            # Green Dragon Florida Downloader (HTML scraping via Squarespace)
            logger.info("Initializing Green Dragon downloader...")
            try:
                green_dragon_downloader = GreenDragonDownloader(
                    output_dir=self.output_dir,
                    azure_manager=self.azure_manager,
                    store_batch=getattr(self, 'green_dragon_batch', None),
                    stores_per_batch=getattr(self, 'green_dragon_stores_per_batch', 5),
                    parallel_stores=getattr(self, 'green_dragon_parallel_stores', 2)
                )
                downloaders['green_dragon'] = {
                    'name': 'Green Dragon',
                    'enabled': True,
                    'downloader': green_dragon_downloader
                }
                batch_info = f" (batch {getattr(self, 'green_dragon_batch', None)})" if getattr(self, 'green_dragon_batch', None) is not None else " (all stores)"
                logger.info(f"Green Dragon: Configured to download {green_dragon_downloader.store_count} stores{batch_info}")
                logger.info(f"Green Dragon: {green_dragon_downloader.total_batches} total batches, {green_dragon_downloader.parallel_stores} parallel downloads")
                try:
                    setattr(green_dragon_downloader, 'write_local', not self.in_memory)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Green Dragon: Could not initialize downloader: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize modular downloaders: {e}")
            return {}
            
        return downloaders
    
    def _get_dispensary_display_name(self, dispensary_id: str) -> str:
        """Get the display name for a dispensary from its ID"""
        dispensary_names = {
            'muv': 'MUV',
            'trulieve': 'Trulieve',
            'sunburn': 'Sunburn Cannabis',
            'cookies': 'Cookies Florida',
            'flowery': 'The Flowery',
            'curaleaf': 'Curaleaf',
            'green_dragon': 'Green Dragon'
        }
        return dispensary_names.get(dispensary_id, dispensary_id.title())
    
    def _set_job_tracking_on_downloaders(self, job_id: str):
        """Set job tracker and job ID on all downloaders for store-level tracking"""
        if not self.job_tracker or not job_id:
            return
        
        for dispensary_id, config in self.downloaders.items():
            downloader = config.get('downloader')
            if downloader:
                downloader.job_tracker = self.job_tracker
                downloader.job_id = job_id
                logger.debug(f"Set job tracking on {dispensary_id} downloader")
    
    def _extract_batches_from_data(self, dispensary: str, filename: str, data: Dict):
        """Extract batch information from menu data and add to batch tracker"""
        try:
            if dispensary == 'muv':
                # MUV data structure: products are in data.products.list array
                products_data = data.get('products', {}) if isinstance(data, dict) else {}
                products = products_data.get('list', []) if isinstance(products_data, dict) else []
                
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    product_id = str(product.get('id', ''))
                    product_name = product.get('name', '')
                    category = product.get('category', {}).get('name', '') if isinstance(product.get('category'), dict) else ''
                    brand = product.get('brand', {}).get('name', '') if isinstance(product.get('brand'), dict) else ''
                    # Strain: strain.name or strain.title, fallback to product name
                    strain_obj = product.get('strain', {}) if isinstance(product.get('strain'), dict) else {}
                    strain_name = strain_obj.get('name', '') or strain_obj.get('title', '') or product_name
                    
                    variants = product.get('variants', [])
                    for variant in variants:
                        if not isinstance(variant, dict):
                            continue
                        variant_id = str(variant.get('id', ''))
                        if product_id and variant_id:
                            self.batch_counter += 1
                            # Construct Azure Data Lake path
                            azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/muv/{os.path.basename(filename)}"
                            self.batch_tracker.append({
                                'index': self.batch_counter,
                                'batch_name': f"{product_id}_{variant_id}",
                                'product_name': product_name,
                                'product_type': category,
                                'dispensary': 'muv',
                                'dispensary_name': self._get_dispensary_display_name('muv'),
                                'filename': os.path.basename(filename),
                                'azure_path': azure_path,
                                'brand': brand,
                                'product_id': product_id,
                                'variant_id': variant_id,
                                'strain': strain_name
                            })
            
            elif dispensary == 'cookies':
                # Cookies data structure: products field contains API response with 'results' array
                products_data = data.get('products', {}) if isinstance(data, dict) else {}
                products = products_data.get('results', []) if isinstance(products_data, dict) else []
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    # For Cookies, batch_name is from meta_data.batch_name (per terprint-config)
                    # e.g., "F26H425S10844-BIG" - NEVER use product ID as batch_name
                    meta_data = product.get('meta_data', {}) if isinstance(product.get('meta_data'), dict) else {}
                    batch_name = str(meta_data.get('batch_name', '') or '')
                    if not batch_name:
                        # Skip products without a real batch_name - do NOT use product ID
                        continue
                    # Strain: tags[0] with fallback to name (per terprint-config)
                    tags = product.get('tags', [])
                    strain_name = tags[0] if isinstance(tags, list) and len(tags) > 0 else product.get('name', '')
                    if batch_name:
                        self.batch_counter += 1
                        # Construct Azure Data Lake path
                        azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/cookies/{os.path.basename(filename)}"
                        self.batch_tracker.append({
                            'index': self.batch_counter,
                            'batch_name': batch_name,
                            'product_name': product.get('name', ''),
                            'product_type': product.get('category', ''),
                            'dispensary': 'cookies',
                            'dispensary_name': self._get_dispensary_display_name('cookies'),
                            'filename': os.path.basename(filename),
                            'azure_path': azure_path,
                            'strain': strain_name
                        })
            
            elif dispensary == 'flowery':
                products = data.get('products', []) if isinstance(data, dict) else []
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    # batch_name: batch_num with fallback to sku (per terprint-config)
                    batch_name = str(product.get('batch_num', '') or product.get('sku', '') or '')
                    if batch_name:
                        categories = product.get('categories', [])
                        category_str = ', '.join(categories) if isinstance(categories, list) else str(categories)
                        # Strain: strain.name with fallback to name (per terprint-config)
                        strain_obj = product.get('strain', {}) if isinstance(product.get('strain'), dict) else {}
                        strain_name = strain_obj.get('name', '') or product.get('name', '')
                        self.batch_counter += 1
                        # Construct Azure Data Lake path
                        azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/flowery/{os.path.basename(filename)}"
                        self.batch_tracker.append({
                            'index': self.batch_counter,
                            'batch_name': batch_name,
                            'product_name': product.get('name', ''),
                            'product_type': category_str,
                            'dispensary': 'flowery',
                            'dispensary_name': self._get_dispensary_display_name('flowery'),
                            'filename': os.path.basename(filename),
                            'azure_path': azure_path,
                            'sku': product.get('sku', ''),
                            'brand': product.get('brand', {}).get('name', '') if isinstance(product.get('brand'), dict) else '',
                            'strain': strain_name
                        })
            
            elif dispensary == 'sunburn':
                products = data.get('products', []) if isinstance(data, dict) else []
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    batch_json = product.get('batchJSON', {})
                    if isinstance(batch_json, str):
                        try:
                            batch_json = json.loads(batch_json)
                        except:
                            pass
                    order_number = batch_json.get('order_number', '') if isinstance(batch_json, dict) else ''
                    if order_number:
                        self.batch_counter += 1
                        # Construct Azure Data Lake path
                        azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/sunburn/{os.path.basename(filename)}"
                        self.batch_tracker.append({
                            'index': self.batch_counter,
                            'batch_name': order_number,
                            'product_name': batch_json.get('product_name', '') if isinstance(batch_json, dict) else '',
                            'product_type': batch_json.get('matrix', '') if isinstance(batch_json, dict) else '',
                            'dispensary': 'sunburn',
                            'dispensary_name': self._get_dispensary_display_name('sunburn'),
                            'filename': os.path.basename(filename),
                            'azure_path': azure_path,
                            'cultivar': ', '.join(batch_json.get('cultivar', [])) if isinstance(batch_json, dict) and isinstance(batch_json.get('cultivar'), list) else ''
                        })
            
            elif dispensary == 'trulieve':
                products = []
                if isinstance(data, dict):
                    if 'products' in data:
                        products = data['products']
                    elif 'combined_products' in data:
                        products = data['combined_products']
                elif isinstance(data, list):
                    products = data
                
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    sku = product.get('sku') or product.get('id') or ''
                    product_name = product.get('name', '')
                    category = product.get('category', '')
                    
                    # Strain: custom_attributes_product[code='strain'].value, fallback split name on ' - ' (per terprint-config)
                    strain_name = ''
                    custom_attrs = product.get('custom_attributes_product', []) or []
                    for attr in custom_attrs:
                        if isinstance(attr, dict) and attr.get('code') == 'strain':
                            strain_name = attr.get('value', '')
                            break
                    if not strain_name and product_name:
                        # Fallback: split name on ' - ' and take first part
                        strain_name = product_name.split(' - ')[0].strip()
                    
                    # Extract from batch_codes field
                    if isinstance(product.get('batch_codes'), list):
                        for batch_code in product.get('batch_codes'):
                            batch_name = f"{sku}_{batch_code}" if sku else str(batch_code)
                            self.batch_counter += 1
                            # Construct Azure Data Lake path
                            azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/trulieve/{os.path.basename(filename)}"
                            self.batch_tracker.append({
                                'index': self.batch_counter,
                                'batch_name': batch_name,
                                'product_name': product_name,
                                'product_type': category,
                                'dispensary': 'trulieve',
                                'dispensary_name': self._get_dispensary_display_name('trulieve'),
                                'filename': os.path.basename(filename),
                                'azure_path': azure_path,
                                'sku': sku,
                                'batch_code': batch_code,
                                'strain': strain_name
                            })
                    
                    # Extract from configurable_options
                    for opt in product.get('configurable_options', []) or []:
                        if opt.get('attribute_code') and 'batch' in opt.get('attribute_code'):
                            for v in opt.get('values', []) or []:
                                label = v.get('label') or v.get('value')
                                if label:
                                    batch_name = f"{sku}_{label}" if sku else str(label)
                                    self.batch_counter += 1
                                    # Construct Azure Data Lake path
                                    azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/trulieve/{os.path.basename(filename)}"
                                    self.batch_tracker.append({
                                        'index': self.batch_counter,
                                        'batch_name': batch_name,
                                        'product_name': product_name,
                                        'product_type': category,
                                        'dispensary': 'trulieve',
                                        'dispensary_name': self._get_dispensary_display_name('trulieve'),
                                        'filename': os.path.basename(filename),
                                        'azure_path': azure_path,
                                        'sku': sku,
                                        'batch_code': label,
                                        'strain': strain_name
                                    })
            
            elif dispensary == 'curaleaf':
                # Curaleaf data structure: products is a list in data.products
                products = data.get('products', []) if isinstance(data, dict) else []
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    # Use product_id as batch identifier (no separate batch number in Curaleaf)
                    product_id = str(product.get('product_id', '') or product.get('product_slug', ''))
                    if product_id:
                        self.batch_counter += 1
                        # Construct Azure Data Lake path
                        azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/curaleaf/{os.path.basename(filename)}"
                        self.batch_tracker.append({
                            'index': self.batch_counter,
                            'batch_name': product_id,
                            'product_name': product.get('name', ''),
                            'product_type': product.get('category', ''),
                            'dispensary': 'curaleaf',
                            'dispensary_name': self._get_dispensary_display_name('curaleaf'),
                            'filename': os.path.basename(filename),
                            'azure_path': azure_path,
                            'sku': product.get('product_slug', ''),
                            'brand': product.get('brand', ''),
                            'strain': product.get('name', '').split(' - ')[0] if ' - ' in product.get('name', '') else product.get('name', ''),
                            'thc_percent': product.get('thc_percent'),
                            'total_terpenes': product.get('total_terpenes_percent'),
                            'top_terpenes': product.get('top_terpenes', ''),
                            'lab_test_url': product.get('lab_test_url', '')
                        })
            elif dispensary == 'green_dragon':
                # Green Dragon data structure: products is a list in data.products
                products = data.get('products', []) if isinstance(data, dict) else []
                store_name = data.get('store_name', '') if isinstance(data, dict) else ''
                store_slug = data.get('store_slug', '') if isinstance(data, dict) else ''
                for product in products:
                    if not isinstance(product, dict):
                        continue
                    product_name = product.get('name', '')
                    if product_name:
                        self.batch_counter += 1
                        azure_path = f"https://{AZURE_STORAGE_ACCOUNT_NAME}.dfs.core.windows.net/{AZURE_CONTAINER_NAME}/green_dragon/{os.path.basename(filename)}"
                        self.batch_tracker.append({
                            'index': self.batch_counter,
                            'batch_name': f"{store_slug}_{product_name}".replace(' ', '_').lower(),
                            'product_name': product_name,
                            'product_type': product.get('category', 'flower'),
                            'dispensary': 'green_dragon',
                            'dispensary_name': self._get_dispensary_display_name('green_dragon'),
                            'filename': os.path.basename(filename),
                            'azure_path': azure_path,
                            'sku': '',
                            'brand': 'Green Dragon',
                            'strain': product_name,
                            'thc_percent': None,
                            'total_terpenes': None,
                            'top_terpenes': '',
                            'lab_test_url': product.get('source_url', '')
                        })
        except Exception as e:
            logger.warning(f"[BATCH] Error extracting batches from {dispensary}/{filename}: {e}")
    
    def download_all_dispensaries(self, parallel: bool = True) -> Dict[str, List[Tuple[str, Dict]]]:
        """Download data from all enabled dispensaries using ONLY modular downloaders"""
        logger.info("STARTING DISPENSARY DATA DOWNLOAD")
        logger.info("=" * 60)
        log_telemetry(logger, "orchestrator_download_start", properties={"mode": "sequential"})
        
        if not self.downloaders:
            logger.error("No downloaders available! Cannot proceed.")
            return {}
        
        enabled_dispensaries = [d_id for d_id, config in self.downloaders.items() if config.get('enabled', True)]
        logger.info(f"Enabled dispensaries: {', '.join(enabled_dispensaries)}")
        logger.info("Download mode: Sequential (ensuring all dispensaries complete before uploads)")
        
        download_results = {}
        
        # Always process dispensaries sequentially to ensure complete processing before uploads
        logger.info("Starting sequential downloads...")
        for dispensary_id, config in self.downloaders.items():
            if config.get('enabled', True):
                try:
                    downloader = config['downloader']
                    
                    # Print to console for immediate feedback
                    sys.stdout.write(f"\n[>>] Starting {config['name']} ({dispensary_id})...\n")
                    sys.stdout.flush()
                    
                    logger.info(f"Starting download for {dispensary_id}...")
                    log_telemetry(logger, "dispensary_download_start", properties={"dispensary": dispensary_id})
                    
                    results = downloader.download()
                    
                    # Extract batches from downloaded data
                    logger.info(f"[BATCH] Extracting batches from {len(results)} files for {dispensary_id}")
                    genetics_count = 0
                    for filepath, data in results:
                        self._extract_batches_from_data(dispensary_id, filepath, data)
                        # Genetics extraction per file
                        if self.enable_genetics and self._genetics_scraper and isinstance(data, (dict, list)):
                            try:
                                source_file = os.path.basename(filepath)
                                extraction = self._genetics_scraper.extract_from_menu(data, dispensary=dispensary_id, source_file=source_file)
                                genetics_count += extraction.unique_strains
                                # Save immediately if configured
                                if self.save_genetics and self._genetics_storage and extraction.genetics_found:
                                    import asyncio
                                    async def _save():
                                        try:
                                            await self._genetics_storage.connect()
                                            await self._genetics_storage.save_genetics(extraction.genetics_found)
                                        except Exception as _e:
                                            logger.warning(f"[GENETICS] Save failed: {_e}")
                                    try:
                                        asyncio.run(_save())
                                    except RuntimeError:
                                        # If an event loop exists, fallback to creating one
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        loop.run_until_complete(_save())
                                        loop.close()
                            except Exception as ge:
                                logger.debug(f"[GENETICS] Extraction error for {dispensary_id}/{source_file}: {ge}")
                    logger.info(f"[BATCH] Total batches collected so far: {len(self.batch_tracker)}")
                    if self.enable_genetics:
                        logger.info(f"[GENETICS] {dispensary_id}: extracted genetics for ~{genetics_count} strains")
                    
                    # Print completion to console
                    sys.stdout.write(f"[OK] {config['name']} completed: {len(results)} files\n")
                    sys.stdout.flush()
                    
                    download_results[dispensary_id] = results
                    self.results['downloads'][dispensary_id] = {
                        'success': True,
                        'files': len(results),
                        'files_list': [os.path.basename(filepath) for filepath, _ in results]
                    }
                    logger.info(f"SUCCESS: {dispensary_id} download completed: {len(results)} files")
                    log_telemetry(logger, "dispensary_download_completed", 
                                  properties={"dispensary": dispensary_id}, 
                                  measurements={"files_count": len(results)})
                except Exception as e:
                    logger.error(f"Failed to download {dispensary_id}: {e}")
                    log_exception(logger, e, context=f"{dispensary_id} download", dispensary_id=dispensary_id)
                    log_telemetry(logger, "dispensary_download_failed", properties={"dispensary": dispensary_id, "error": str(e)})
                    download_results[dispensary_id] = []
                    self.results['downloads'][dispensary_id] = {
                        'success': False,
                        'error': str(e)
                    }
                    self.results['errors'].append(f"{dispensary_id}: {str(e)}")
        
        # Summary of downloads
        total_files = sum(len(files) for files in download_results.values())
        successful_dispensaries = sum(1 for files in download_results.values() if files)
        
        logger.info(f"\nDOWNLOAD SUMMARY:")
        logger.info(f"   Dispensaries processed: {successful_dispensaries}/{len(enabled_dispensaries)}")
        logger.info(f"   Total files downloaded: {total_files}")
        
        return download_results
    
    def upload_to_azure(self, download_results: Dict[str, List[Tuple[str, Dict]]], delete_after_upload: bool = False, dry_run: bool = False, upload_to_eventhouse: bool = False) -> bool:
        """Upload downloaded files to Azure Data Lake (and optionally Event House)"""
        logger.info("\nSTARTING AZURE DATA LAKE UPLOAD")
        logger.info("=" * 60)
        
        # Skip Event House upload unless explicitly requested
        if not upload_to_eventhouse:
            logger.info("Event House upload disabled (use --eventhouse flag to enable)")
            logger.info("Files will be uploaded to Azure Data Lake only")
            return True
        
        try:
            # Import Event House uploader
            try:
                from uploadToEventhouse import EventHouseUploader
            except ImportError:
                sys.path.insert(0, os.path.join(terprint_python_dir, "menumover"))
                from uploadToEventhouse import EventHouseUploader
            
            # Validate configuration
            if not validate_config():
                logger.error("Azure configuration validation failed")
                return False
            
            # Initialize Event House uploader
            logger.info(f"Connecting to Event House: {EVENTHOUSE_CLUSTER}")
            logger.info(f"Database: {EVENTHOUSE_DATABASE}, Table: {EVENTHOUSE_TABLE}")
            
            uploader = EventHouseUploader(
                cluster=EVENTHOUSE_CLUSTER,
                database=EVENTHOUSE_DATABASE,
                table=EVENTHOUSE_TABLE,
                tenant_id=AZURE_TENANT_ID,
                client_id=AZURE_CLIENT_ID,
                client_secret=AZURE_CLIENT_SECRET,
                use_azure_cli=USE_AZURE_CLI,
                column_name=EVENTHOUSE_COLUMN
            )
            
            # Test connection
            logger.info("Testing Event House connection...")
            if not uploader.test_connection():
                logger.error("Could not connect to Event House")
                return False
            
            logger.info("Connected to Event House successfully")
            
            # Collect all files to upload
            all_files_to_upload = []
            for dispensary_id, files in download_results.items():
                if not files:
                    logger.info(f"Skipping {dispensary_id}: No files to upload")
                    continue
                    
                for filepath, data in files:
                    all_files_to_upload.append((dispensary_id, filepath, data))
            
            if not all_files_to_upload:
                logger.info("No files to upload")
                return True
            
            logger.info(f"Uploading {len(all_files_to_upload)} files in parallel...")
            
            # Upload files in parallel
            upload_success = True
            total_uploads = len(all_files_to_upload)
            successful_uploads = 0
            
            def upload_single_file(upload_tuple):
                """Upload a single file to Event House"""
                dispensary_id, filepath, data = upload_tuple
                filename = os.path.basename(filepath)
                
                try:
                    logger.info(f"   Uploading {filename} to Event House...")
                    
                    # Add source metadata
                    source_info = {
                        'dispensary': dispensary_id,
                        'filename': filename,
                        'local_path': filepath,
                        'file_size': os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    }
                    
                    # Upload to Event House (or simulate if dry_run)
                    if dry_run:
                        logger.info(f"   DRY-RUN: Simulating upload of {filename}")
                        success = True
                    else:
                        success = uploader.upload_json(data, source_info)
                    
                    if success:
                        file_size = source_info['file_size']
                        logger.info(f"   SUCCESS: {filename} queued for ingestion ({file_size:,} bytes)")
                        # Delete file after successful upload if requested
                        if delete_after_upload and os.path.exists(filepath) and not dry_run:
                            try:
                                os.remove(filepath)
                                logger.info(f"   Deleted local file after upload: {filename}")
                            except Exception as e:
                                logger.warning(f"   Could not delete {filename}: {e}")
                        return True
                    else:
                        logger.error(f"   ERROR: Failed to upload {filename}")
                        return False
                        
                except Exception as e:
                    logger.error(f"   ERROR: Error uploading {filename}: {e}")
                    return False
            
            # Process uploads in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_file = {
                    executor.submit(upload_single_file, upload_tuple): upload_tuple[1]
                    for upload_tuple in all_files_to_upload
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            successful_uploads += 1
                        else:
                            upload_success = False
                    except Exception as e:
                        logger.error(f"   ERROR: Exception uploading {os.path.basename(filepath)}: {e}")
                        upload_success = False
            
            # Upload summary
            logger.info(f"\nUPLOAD SUMMARY:")
            logger.info(f"   Files uploaded: {successful_uploads}/{total_uploads}")
            logger.info(f"   Upload success rate: {(successful_uploads/total_uploads*100):.1f}%" if total_uploads > 0 else "   No files to upload")
            
            return upload_success
            
        except ImportError as e:
            logger.error(f"Could not import Azure modules: {e}")
            self.results['errors'].append(f"Azure import error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Azure upload failed: {e}")
            self.results['errors'].append(f"Azure upload: {str(e)}")
            return False
    
    def upload_existing_files(self) -> bool:
        """Upload existing downloaded files from the output directory to Azure Data Lake and optionally Event House"""
        upload_to_eventhouse = getattr(self, 'upload_to_eventhouse', False)
        
        if not upload_to_eventhouse:
            logger.info("Event House upload disabled (use --eventhouse flag to enable)")
            logger.info("Files remain in local directory")
            return True
        
        logger.info("UPLOADING EXISTING FILES TO AZURE EVENT HOUSE")
        logger.info("=" * 60)
        
        try:
            # Import Event House uploader
            logger.info("Importing EventHouseUploader...")
            try:
                try:
                    from uploadToEventhouse import EventHouseUploader
                except ImportError:
                    sys.path.insert(0, os.path.join(terprint_python_dir, "menumover"))
                    from uploadToEventhouse import EventHouseUploader
                logger.info("[OK] EventHouseUploader imported successfully")
            except ImportError as import_e:
                logger.error(f"[FAIL] Failed to import EventHouseUploader: {import_e}")
                logger.error("Check that uploadToEventhouse.py exists and azure-kusto packages are installed")
                return False
            
            # Validate configuration
            logger.info("Validating Azure configuration...")
            if not validate_config():
                logger.error("Azure configuration validation failed")
                return False
            logger.info("[OK] Azure configuration validated successfully")
            
            # Initialize Event House uploader
            logger.info(f"Connecting to Event House: {EVENTHOUSE_CLUSTER}")
            logger.info(f"Database: {EVENTHOUSE_DATABASE}, Table: {EVENTHOUSE_TABLE}")
            
            try:
                uploader = EventHouseUploader(
                    cluster=EVENTHOUSE_CLUSTER,
                    database=EVENTHOUSE_DATABASE,
                    table=EVENTHOUSE_TABLE,
                    tenant_id=AZURE_TENANT_ID,
                    client_id=AZURE_CLIENT_ID,
                    client_secret=AZURE_CLIENT_SECRET,
                    use_azure_cli=USE_AZURE_CLI,
                    column_name=EVENTHOUSE_COLUMN
                )
                logger.info("[OK] EventHouseUploader initialized")
            except Exception as init_e:
                logger.error(f"[FAIL] Failed to initialize EventHouseUploader: {init_e}")
                logger.error("This could be due to invalid credentials, network issues, or Event House service problems")
                return False
            
            # Test connection
            logger.info("Testing Event House connection...")
            try:
                if not uploader.test_connection():
                    logger.error("Could not connect to Event House")
                    logger.error("Possible causes: invalid credentials, network issues, or Event House service unavailable")
                    return False
                logger.info("[OK] Connected to Event House successfully")
            except Exception as conn_e:
                logger.error(f"[FAIL] Event House connection test failed: {conn_e}")
                logger.error("Check your Azure credentials and Event House configuration")
                return False
            
            # Find the most recent download files
            all_files_to_upload = []
            download_results = {}  # Track downloads for unified JSON creation
            
            # Look for JSON files in subdirectories (muv, trulieve, etc.)
            if os.path.exists(self.output_dir):
                for root, dirs, files in os.walk(self.output_dir):
                    for file in files:
                        if file.endswith('.json'):
                            filepath = os.path.join(root, file)
                            
                            # Determine dispensary from directory structure
                            relative_path = os.path.relpath(root, self.output_dir)
                            dispensary_id = relative_path.split(os.sep)[0] if os.sep in relative_path else 'unknown'
                            
                            try:
                                # Load JSON data
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                
                                all_files_to_upload.append((dispensary_id, filepath, data))
                                
                                # Build download_results for unified JSON
                                if dispensary_id not in download_results:
                                    download_results[dispensary_id] = []
                                download_results[dispensary_id].append((filepath, data))
                                logger.info(f"Found file to upload: {os.path.basename(filepath)} ({dispensary_id})")
                                
                            except Exception as e:
                                logger.warning(f"Could not load {filepath}: {e}")
                                continue
            
            if not all_files_to_upload:
                logger.info("No JSON files found to upload")
                return True
            
            logger.info(f"Uploading {len(all_files_to_upload)} existing files in parallel...")
            
            # Upload files in parallel
            upload_success = True
            total_uploads = len(all_files_to_upload)
            successful_uploads = 0
            
            def upload_single_file(upload_tuple):
                """Upload a single file to Event House"""
                dispensary_id, filepath, data = upload_tuple
                filename = os.path.basename(filepath)
                
                try:
                    logger.info(f"   Uploading {filename} to Event House...")
                    
                    # Add source metadata
                    source_info = {
                        'dispensary': dispensary_id,
                        'filename': filename,
                        'local_path': filepath,
                        'file_size': os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    }
                    
                    # Upload to Event House
                    success = uploader.upload_json(data, source_info)
                    
                    if success:
                        file_size = source_info['file_size']
                        logger.info(f"   SUCCESS: {filename} queued for ingestion ({file_size:,} bytes)")
                        return True
                    else:
                        logger.error(f"   ERROR: Failed to upload {filename}")
                        return False
                        
                except Exception as e:
                    logger.error(f"   ERROR: Error uploading {filename}: {e}")
                    return False
            
            # Process uploads in parallel
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_file = {
                    executor.submit(upload_single_file, upload_tuple): upload_tuple[1]
                    for upload_tuple in all_files_to_upload
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        success = future.result()
                        if success:
                            successful_uploads += 1
                        else:
                            upload_success = False
                    except Exception as e:
                        logger.error(f"   ERROR: Exception uploading {os.path.basename(filepath)}: {e}")
                        upload_success = False
            
            # Upload summary
            logger.info(f"\nUPLOAD SUMMARY:")
            logger.info(f"   Files uploaded: {successful_uploads}/{total_uploads}")
            logger.info(f"   Upload success rate: {(successful_uploads/total_uploads*100):.1f}%" if total_uploads > 0 else "   No files to upload")
            
            return upload_success
            
        except ImportError as e:
            logger.error(f"Could not import Azure modules: {e}")
            return False
        except Exception as e:
            logger.error(f"Azure upload failed: {e}")
            return False
    
    def run_full_pipeline(self, parallel_downloads: bool = True, upload_to_azure: bool = True) -> Dict:
        """Run the complete dispensary data pipeline"""
        start_time = time.time()
        
        mode_name = "DEVELOPMENT" if self.dev_mode else "PRODUCTION"
        enabled_dispensaries = [name for name, config in self.downloaders.items() if config.get('enabled', True)]
        disabled_dispensaries = [name for name, config in self.downloaders.items() if not config.get('enabled', True)]
        
        # Calculate total stores and categories across all enabled dispensaries
        total_stores = 0
        total_categories = 0
        dispensary_details = []
        for dispensary_id, config in self.downloaders.items():
            if config.get('enabled', True):
                downloader = config.get('downloader')
                store_count = 0
                category_count = 0
                if hasattr(downloader, 'get_store_configs'):
                    stores = downloader.get_store_configs()
                    store_count = len(stores) if stores else 0
                elif hasattr(downloader, 'store_ids') and downloader.store_ids:
                    store_count = len(downloader.store_ids)
                elif hasattr(downloader, 'location_slugs') and downloader.location_slugs:
                    store_count = len(downloader.location_slugs)
                
                # Check for category IDs (Trulieve)
                if hasattr(downloader, 'category_ids') and downloader.category_ids:
                    category_count = len(downloader.category_ids)
                    total_categories += category_count
                
                total_stores += store_count
                dispensary_details.append({
                    'id': dispensary_id,
                    'name': config.get('name', dispensary_id),
                    'stores': store_count,
                    'categories': category_count
                })
        
        print()  # Empty line for console output only
        logger.info("=" * 60)
        logger.info("   DISPENSARY DATA ORCHESTRATOR")
        logger.info("=" * 60)
        print()  # Empty line for console output only
        logger.info(f"[*] DOWNLOAD STARTING")
        logger.info(f"    Mode: {mode_name}")
        logger.info(f"    Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()  # Empty line for console output only
        logger.info(f"[*] MODULES INITIALIZED")
        logger.info(f"    Modular downloaders: {'YES' if MODULAR_DOWNLOADERS_AVAILABLE else 'NO'}")
        logger.info(f"    Azure Data Lake: {'YES' if self.azure_manager else 'NO'}")
        logger.info(f"    Job Tracker: {'YES' if self.job_tracker else 'NO'}")
        print()  # Empty line for console output only
        logger.info(f"[*] DISPENSARY CONFIGURATION")
        logger.info(f"    Total dispensaries: {len(enabled_dispensaries)}")
        logger.info(f"    Total stores: {total_stores}")
        if total_categories > 0:
            logger.info(f"    Total categories: {total_categories}")
        print()  # Empty line for console output only
        logger.info(f"    Enabled dispensaries:")
        for detail in dispensary_details:
            if detail['categories'] > 0:
                logger.info(f"      - {detail['name']}: {detail['stores']} stores x {detail['categories']} categories = {detail['stores'] * detail['categories']} combinations")
            else:
                logger.info(f"      - {detail['name']}: {detail['stores']} stores")
        if disabled_dispensaries:
            logger.info(f"    Disabled dispensaries: {', '.join(disabled_dispensaries)}")
        print()  # Empty line for console output only
        logger.info(f"[*] PIPELINE SETTINGS")
        logger.info(f"    Upload to Azure: {upload_to_azure}")
        logger.info(f"    Parallel downloads: {parallel_downloads}")
        logger.info(f"    Output directory: {self.output_dir}")
        logger.info("=" * 60)
        
        # Log job start with full configuration to Application Insights
        log_operation(
            logger,
            operation_name="orchestrator_job_start",
            status="started",
            duration_ms=0,
            mode=mode_name,
            output_dir=self.output_dir,
            upload_to_azure=upload_to_azure,
            parallel_downloads=parallel_downloads,
            modular_downloaders=MODULAR_DOWNLOADERS_AVAILABLE,
            enabled_dispensary_count=len(enabled_dispensaries),
            enabled_dispensaries=", ".join(enabled_dispensaries),
            disabled_dispensary_count=len(disabled_dispensaries)
        )
        
        log_telemetry(logger, "orchestrator_pipeline_start", 
                      properties={"mode": mode_name, "upload_to_azure": str(upload_to_azure)}, 
                      measurements={"dispensary_count": len(enabled_dispensaries)})
        
        # Create job in tracker for restart capability (skip if resuming an existing job)
        if self.job_tracker and not self.current_job_id:
            try:
                # Build stores config for each dispensary using get_store_configs method
                stores_config = {}
                for dispensary_id, config in self.downloaders.items():
                    if config.get('enabled', True):
                        downloader = config.get('downloader')
                        if hasattr(downloader, 'get_store_configs'):
                            stores_config[dispensary_id] = downloader.get_store_configs()
                        elif hasattr(downloader, 'store_ids') and downloader.store_ids:
                            stores_config[dispensary_id] = downloader.store_ids
                        elif hasattr(downloader, 'location_slugs') and downloader.location_slugs:
                            stores_config[dispensary_id] = downloader.location_slugs
                        else:
                            stores_config[dispensary_id] = ['all']  # Single "store" representing all data
                
                job_name = f"MenuDownload_{mode_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.current_job_id = self.job_tracker.create_job(
                    job_name=job_name,
                    dispensaries=enabled_dispensaries,
                    stores_config=stores_config,
                    config={'mode': mode_name, 'upload_to_azure': upload_to_azure}
                )
                self.job_tracker.start_job(self.current_job_id)
                
                # Set job tracker and job ID on all downloaders for store-level tracking
                self._set_job_tracking_on_downloaders(self.current_job_id)
                
                logger.info(f"[JOB] Job tracking started: {self.current_job_id}")
                
                # Log store counts per dispensary
                for disp_id, stores in stores_config.items():
                    logger.info(f"   {disp_id}: {len(stores)} stores registered")
                    
            except Exception as e:
                logger.warning(f"Could not create job tracker entry: {e}")
        elif self.current_job_id:
            logger.info(f"[JOB] Resuming job: {self.current_job_id}")
        
        # Phase 1: Download from dispensaries
        logger.info("\nPHASE 1: DOWNLOADING DATA")
        
        # Print to console for immediate feedback
        sys.stdout.write("\n" + "=" * 70 + "\n")
        sys.stdout.write("PHASE 1: DOWNLOADING DATA FROM DISPENSARIES\n")
        sys.stdout.write("=" * 70 + "\n")
        sys.stdout.flush()
        
        download_start = time.time()
        download_results = self.download_all_dispensaries(parallel=parallel_downloads)
        download_duration = (time.time() - download_start) * 1000
        
        log_operation(
            logger,
            operation_name="dispensary_downloads",
            status="success" if download_results else "failed",
            duration_ms=download_duration,
            dispensary_count=len([d for d in self.downloaders.values() if d.get('enabled', True)]),
            file_count=sum(len(files) for files in download_results.values()),
            parallel_mode=parallel_downloads
        )
        
        # Phase 2: Upload to Azure (if enabled)
        azure_success = True
        # Create and upload Trulieve combined files and batch codes
        try:
            self._create_and_upload_trulieve_batch(download_results)
        except Exception as e:
            logger.warning(f"Could not create/upload Trulieve batch files: {e}")
        
        # Extract and consolidate batches from all dispensaries
        logger.info(f"[BATCHES] Starting batch consolidation. Batch tracker has {len(self.batch_tracker)} batches")
        try:
            self._extract_and_consolidate_batches(download_results)
            logger.info(f"[BATCHES] Batch consolidation completed successfully")
        except Exception as e:
            logger.critical(f"[BATCHES] CRITICAL - Failed to extract and consolidate batches: {e}", exc_info=True)

        if upload_to_azure:
            logger.info("\nPHASE 2: UPLOADING TO AZURE")
            # pass deletion and dry-run flags from self if present
            delete_flag = getattr(self, 'delete_after_upload', False)
            dry_run_flag = getattr(self, 'dry_run_upload', False)
            eventhouse_flag = getattr(self, 'upload_to_eventhouse', False)
            
            upload_start = time.time()
            azure_success = self.upload_to_azure(download_results, delete_after_upload=delete_flag, dry_run=dry_run_flag, upload_to_eventhouse=eventhouse_flag)
            upload_duration = (time.time() - upload_start) * 1000
            
            log_operation(
                logger,
                operation_name="azure_upload",
                status="success" if azure_success else "failed",
                duration_ms=upload_duration,
                delete_after_upload=delete_flag,
                dry_run=dry_run_flag
            )
        else:
            logger.info("\nPHASE 2: SKIPPING AZURE UPLOAD (DISABLED)")
        
        # Calculate summary
        end_time = time.time()
        duration = end_time - start_time
        
        total_files = sum(len(files) for files in download_results.values())
        successful_downloads = sum(1 for dispensary_id, files in download_results.items() 
                                 if files and self.results['downloads'].get(dispensary_id, {}).get('success', False))
        
        # Get unique batch count
        unique_batch_names = set(b.get('batch_name') for b in self.batch_tracker if b.get('batch_name'))
        
        self.results['summary'] = {
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.fromtimestamp(end_time).isoformat(),
            'duration_seconds': round(duration, 2),
            'total_dispensaries': len([d for d in self.downloaders.values() if d.get('enabled', True)]),
            'successful_downloads': successful_downloads,
            'total_files_downloaded': total_files,
            'total_unique_batches': len(unique_batch_names),
            'azure_upload_attempted': upload_to_azure,
            'azure_upload_success': azure_success,
            'overall_success': successful_downloads > 0 and (not upload_to_azure or azure_success),
            'modular_downloaders_used': MODULAR_DOWNLOADERS_AVAILABLE
        }
        
        # Log pipeline completion telemetry
        mode_name = "DEVELOPMENT" if self.dev_mode else "PRODUCTION"
        log_telemetry(logger, "orchestrator_pipeline_completed", 
                      properties={
                          "mode": mode_name,
                          "overall_success": str(self.results['summary']['overall_success'])
                      }, 
                      measurements={
                          "duration_seconds": duration,
                          "total_dispensaries": self.results['summary']['total_dispensaries'],
                          "successful_downloads": successful_downloads,
                          "total_files": total_files,
                          "total_unique_batches": self.results['summary'].get('total_unique_batches', 0)
                      })
        
        # Complete job in tracker
        if self.job_tracker and self.current_job_id:
            try:
                error_msg = "; ".join(self.results['errors']) if self.results['errors'] else None
                self.job_tracker.complete_job(self.current_job_id, error_msg)
                
                # Log batch statistics to job tracker
                unique_batch_count = self.results['summary'].get('total_unique_batches', 0)
                if unique_batch_count > 0:
                    logger.info(f"[JOB] Extracted {unique_batch_count} unique batches")
                
                self.job_tracker.print_job_summary(self.current_job_id)
            except Exception as e:
                logger.warning(f"Could not complete job tracker entry: {e}")
        
        # Save results to Azure Data Lake
        self._save_results()
        
        # Rebuild stock index after all dispensaries complete downloads
        self._rebuild_stock_index()
        
        # Optionally refresh genetics index after pipeline
        try:
            if getattr(self, 'enable_genetics', False) and self._genetics_storage:
                import asyncio
                async def _refresh():
                    await self._genetics_storage.connect()
                    await self._genetics_storage.refresh_index()
                try:
                    asyncio.run(_refresh())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(_refresh())
                    loop.close()
                logger.info("[GENETICS] Index refreshed for recommender usage")
        except Exception as e:
            logger.warning(f"[GENETICS] Index refresh failed: {e}")
        
        # Print final summary
        self._print_summary()
        
        return self.results
    
    def _save_results(self):
        """Save orchestrator results to Azure Data Lake (no local files)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not self.azure_manager:
            logger.warning("[!] Azure Data Lake not available, skipping results save")
            return
        
        # Save overall results to Azure Data Lake
        results_filename = f"orchestrator_results_{timestamp}.json"
        azure_path = f"orchestrator_results/{results_filename}"
        
        try:
            results_json = json.dumps(self.results, indent=2, ensure_ascii=False)
            file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
            file_client.upload_data(data=results_json, overwrite=True)
            logger.info(f"[OK] Overall results uploaded to Azure: {azure_path}")
            log_telemetry(logger, "orchestrator_results_saved", properties={"path": azure_path})
        except Exception as e:
            logger.error(f"[FAIL] Failed to upload overall results: {e}")
            log_exception(logger, e, context="Save overall results")
        
        # Save per-dispensary downloads to Azure
        for dispensary_id, info in self.results.get('downloads', {}).items():
            try:
                downloads_filename = f"{dispensary_id}_downloads_{timestamp}.json"
                azure_path = f"orchestrator_results/{dispensary_id}/{downloads_filename}"
                downloads_json = json.dumps(info, indent=2, ensure_ascii=False)
                file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
                file_client.upload_data(data=downloads_json, overwrite=True)
                logger.info(f"[OK] {dispensary_id} downloads uploaded to Azure: {azure_path}")
            except Exception as e:
                logger.error(f"[FAIL] Failed to upload downloads for {dispensary_id}: {e}")

        # Save per-dispensary uploads to Azure
        for dispensary_id, info in self.results.get('uploads', {}).items():
            try:
                uploads_filename = f"{dispensary_id}_uploads_{timestamp}.json"
                azure_path = f"orchestrator_results/{dispensary_id}/{uploads_filename}"
                uploads_json = json.dumps(info, indent=2, ensure_ascii=False)
                file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
                file_client.upload_data(data=uploads_json, overwrite=True)
                logger.info(f"[OK] {dispensary_id} uploads uploaded to Azure: {azure_path}")
            except Exception as e:
                logger.error(f"[FAIL] Failed to upload uploads for {dispensary_id}: {e}")
    
    def _rebuild_stock_index(self):
        """
        Rebuild the stock index after menu downloads complete.
        Triggers the stock API to rebuild its in-memory index with latest menu data.
        """
        try:
            import requests
            
            # Get APIM subscription key from environment
            apim_key = os.environ.get('APIM_SUBSCRIPTION_KEY') or os.environ.get('API_KEY')
            if not apim_key:
                logger.warning("[STOCK] APIM_SUBSCRIPTION_KEY not set - skipping stock index rebuild")
                return
            
            # Build the rebuild endpoint URL
            apim_gateway = os.environ.get('APIM_GATEWAY_URL', 'https://apim-terprint-dev.azure-api.net')
            rebuild_url = f"{apim_gateway}/menus/api/stock/build-index"
            
            logger.info(f"[STOCK] Triggering stock index rebuild at: {rebuild_url}")
            
            # Make the request to rebuild the stock index
            headers = {
                'Ocp-Apim-Subscription-Key': apim_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(rebuild_url, headers=headers, timeout=30, json={})
            
            if response.status_code in [200, 202]:
                logger.info(f"[STOCK] Index rebuild triggered successfully (HTTP {response.status_code})")
                try:
                    result = response.json()
                    logger.info(f"[STOCK] Rebuild response: {result.get('message', result.get('status', 'OK'))}")
                    if result.get('status') == 'building':
                        logger.info(f"[STOCK] Index build in progress - {result.get('items_processed', 0)} items processed")
                except:
                    pass  # Response might not be JSON
                
                log_telemetry(logger, "stock_index_rebuild_triggered", 
                            properties={"status": "success"}, 
                            measurements={"response_code": response.status_code})
            else:
                logger.warning(f"[STOCK] Index rebuild failed with status {response.status_code}: {response.text}")
                log_telemetry(logger, "stock_index_rebuild_failed", 
                            properties={"status": f"http_{response.status_code}", "error": response.text[:200]})
        
        except requests.exceptions.RequestException as e:
            logger.warning(f"[STOCK] Failed to trigger stock index rebuild: {e}")
            log_exception(logger, e, context="Stock index rebuild")
        except Exception as e:
            logger.warning(f"[STOCK] Unexpected error during stock index rebuild: {e}")
            log_exception(logger, e, context="Stock index rebuild")

    def _create_and_upload_trulieve_batch(self, download_results: Dict[str, List[Tuple[str, Dict]]]):
        """Build combined Trulieve JSON (all stores), products-only JSON and a deduped batch-codes JSON.
        Save locally under `docs/` and upload to Azure Data Lake when available.
        """
        try:
            # Detect Azure Functions environment - don't create local dirs
            is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
            
            # Only create local docs_dir if NOT in Azure Functions and NOT in in_memory mode
            docs_dir = None
            if not is_azure_functions and not getattr(self, 'in_memory', False):
                docs_dir = os.path.join(current_dir, 'docs')
                os.makedirs(docs_dir, exist_ok=True)

            trulieve_files = download_results.get('trulieve') or []
            if not trulieve_files:
                logger.info("No Trulieve files found in download results; skipping batch creation")
                return

            combined_by_store = {}
            combined_products = []

            for filepath, data in trulieve_files:
                # Derive store key from filename or data
                store_key = os.path.splitext(os.path.basename(filepath))[0]
                combined_by_store[store_key] = data

                # Collect any product lists we can find
                if isinstance(data, dict):
                    if 'products' in data and isinstance(data['products'], list):
                        combined_products.extend(data['products'])
                    elif 'combined_products' in data and isinstance(data['combined_products'], list):
                        combined_products.extend(data['combined_products'])
                    else:
                        # try to find first list value
                        for v in data.values():
                            if isinstance(v, list):
                                combined_products.extend(v)
                                break
                elif isinstance(data, list):
                    combined_products.extend(data)

            # Deduplicate products by SKU when possible
            unique_products = {}
            for p in combined_products:
                if not isinstance(p, dict):
                    key = json.dumps(p, sort_keys=True)
                else:
                    key = p.get('sku') or p.get('id') or json.dumps(p, sort_keys=True)
                unique_products[key] = p

            products_list = list(unique_products.values())

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            combined_filename = os.path.join(docs_dir, f'trulieve_combined_{timestamp}.json') if docs_dir else None
            products_filename = os.path.join(docs_dir, f'trulieve_products_{timestamp}.json') if docs_dir else None

            # Either save files locally or keep in-memory and upload directly
            combined_payload = {'stores': combined_by_store}
            products_payload = {'products': products_list}

            if docs_dir and not getattr(self, 'in_memory', False):
                # Save combined stores JSON
                with open(combined_filename, 'w', encoding='utf-8') as cf:
                    json.dump(combined_payload, cf, indent=2, ensure_ascii=False)
                logger.info(f"Saved Trulieve combined JSON to: {combined_filename}")

                # Save products-only JSON
                with open(products_filename, 'w', encoding='utf-8') as pf:
                    json.dump(products_payload, pf, indent=2, ensure_ascii=False)
                logger.info(f"Saved Trulieve products-only JSON to: {products_filename} ({len(products_list)} products)")
            else:
                logger.info(f"In-memory mode: prepared combined and products payloads (not written to disk)")

            # Build batch codes list from products
            batch_codes = []
            for p in products_list:
                if not isinstance(p, dict):
                    continue
                sku = p.get('sku') or p.get('id') or ''
                # direct batch_codes field
                if isinstance(p.get('batch_codes'), list):
                    for b in p.get('batch_codes'):
                        batch_codes.append(f"{sku}_{b}" if sku else str(b))
                # configurable options
                for opt in p.get('configurable_options', []) or []:
                    if opt.get('attribute_code') and 'batch' in opt.get('attribute_code'):
                        for v in opt.get('values', []) or []:
                            label = v.get('label') or v.get('value')
                            if label:
                                batch_codes.append(f"{sku}_{label}" if sku else str(label))

            batch_codes = sorted(set(batch_codes))
            batch_obj = {
                'timestamp': datetime.now().isoformat(),
                'dispensary': 'trulieve',
                'batch_codes': batch_codes,
                'count': len(batch_codes)
            }

            batch_filename = os.path.join(docs_dir, f'trulieve_batch_codes_{timestamp}.json') if docs_dir else None
            if docs_dir and not getattr(self, 'in_memory', False):
                with open(batch_filename, 'w', encoding='utf-8') as bf:
                    json.dump(batch_obj, bf, indent=2, ensure_ascii=False)
                logger.info(f"Saved Trulieve batch codes to: {batch_filename} ({len(batch_codes)} entries)")

            # Attempt to upload to Azure Data Lake if available
            if self.azure_manager:
                try:
                    date_folder = datetime.now().strftime("%Y/%m/%d")
                    # Always upload from memory in Azure Functions or in_memory mode
                    # Use local files only when they exist
                    targets = [
                        (combined_payload, f"trulieve_combined_{timestamp}.json"),
                        (products_payload, f"trulieve_products_{timestamp}.json"),
                        (batch_obj, f"trulieve_batch_codes_{timestamp}.json")
                    ]

                    for payload, target_name in targets:
                        azure_path = f"dispensaries/trulieve/{date_folder}/{target_name}"
                        try:
                            if hasattr(self.azure_manager, 'save_json_to_data_lake'):
                                self.azure_manager.save_json_to_data_lake(json_data=payload, file_path=azure_path, overwrite=True)
                            else:
                                file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
                                file_client.upload_data(data=json.dumps(payload, ensure_ascii=False), overwrite=True)
                            logger.info(f"Uploaded {target_name} to Azure Data Lake: {azure_path}")
                        except Exception as up_e:
                            logger.warning(f"Failed to upload {target_name} to Azure: {up_e}")
                except Exception as e:
                    logger.warning(f"Error while uploading Trulieve batch files to Azure: {e}")

        except Exception as e:
            logger.warning(f"Error building Trulieve combined/products/batch files: {e}")
    
    def _extract_and_consolidate_batches(self, download_results: Dict[str, List[Tuple[str, Dict]]]):
        """Consolidate batches collected during downloads into a single daily file.
        Appends only new batches to existing file if one exists for today.
        """
        try:
            # Detect Azure Functions environment - don't create local dirs
            is_azure_functions = os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None
            
            # Only create local docs_dir if NOT in Azure Functions and NOT in in_memory mode
            batch_filename = None
            if not is_azure_functions and not getattr(self, 'in_memory', False):
                docs_dir = os.path.join(current_dir, 'docs')
                os.makedirs(docs_dir, exist_ok=True)
                today = datetime.now().strftime('%Y%m%d')
                batch_filename = os.path.join(docs_dir, f'consolidated_batches_{today}.json')
            
            # Use today's date for filename
            today = datetime.now().strftime('%Y%m%d')
            
            # Load existing batches from Azure first (if available), then local file
            existing_batches_dict = {}
            existing_count = 0
            existing_data = None
            
            # Try to download from Azure first
            azure_path = f"batches/consolidated_batches_{today}.json"
            old_azure_path = f"batches/{datetime.now().strftime('%Y/%m/%d')}/consolidated_batches_{today}.json"
            
            if self.azure_manager:
                try:
                    # Try new path first
                    if hasattr(self.azure_manager, 'file_system_client'):
                        file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
                        try:
                            download = file_client.download_file()
                            content = download.readall()
                            existing_data = json.loads(content)
                            logger.info(f"[BATCHES] Downloaded existing batch file from Azure: {azure_path}")
                        except Exception as e:
                            if 'PathNotFound' in str(e) or 'ResourceNotFound' in str(e):
                                # Try old path with date folders for backward compatibility
                                logger.debug(f"[BATCHES] File not found at new path, trying old path: {old_azure_path}")
                                try:
                                    file_client = self.azure_manager.file_system_client.get_file_client(old_azure_path)
                                    download = file_client.download_file()
                                    content = download.readall()
                                    existing_data = json.loads(content)
                                    logger.info(f"[BATCHES] Downloaded existing batch file from old Azure path: {old_azure_path}")
                                    logger.info(f"[BATCHES] Will migrate to new path: {azure_path}")
                                except Exception as e2:
                                    logger.debug(f"[BATCHES] No existing batch file in Azure (first run of the day)")
                            else:
                                logger.debug(f"[BATCHES] Azure download error: {e}")
                except Exception as e:
                    logger.debug(f"[BATCHES] Could not download from Azure: {e}")
            
            # Fallback to local file if Azure download failed (only if local file path exists)
            if existing_data is None and batch_filename and os.path.exists(batch_filename):
                try:
                    with open(batch_filename, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    logger.info(f"[BATCHES] Loaded existing batches from local file: {batch_filename}")
                except Exception as e:
                    logger.warning(f"[BATCHES] Could not load existing batch file: {e}")
            
            # Convert existing batches to dict for fast lookup
            if existing_data:
                for batch in existing_data.get('batches', []):
                    if 'batch_name' in batch:
                        existing_batches_dict[batch['batch_name']] = batch
                existing_count = len(existing_batches_dict)
                logger.info(f"[BATCHES] Found {existing_count} existing batches")
            
            # Filter out batches that already exist
            new_batches = []
            for batch in self.batch_tracker:
                batch_name = batch.get('batch_name')
                if batch_name and batch_name not in existing_batches_dict:
                    new_batches.append(batch)
                    existing_batches_dict[batch_name] = batch
            
            # Combine all batches (existing + new)
            all_batches = list(existing_batches_dict.values())
            
            # Sort by dispensary, then batch_name
            all_batches.sort(key=lambda x: (x.get('dispensary', ''), x.get('batch_name', '')))
            
            # Reindex all batches
            for idx, batch in enumerate(all_batches, start=1):
                batch['index'] = idx
            
            # Create consolidated output
            consolidated_data = {
                'generated_at': datetime.now().isoformat(),
                'date': today,
                'total_batches': len(all_batches),
                'new_batches_added': len(new_batches),
                'existing_batches': existing_count,
                'batches_by_dispensary': {
                    'muv': len([b for b in all_batches if b.get('dispensary') == 'muv']),
                    'cookies': len([b for b in all_batches if b.get('dispensary') == 'cookies']),
                    'flowery': len([b for b in all_batches if b.get('dispensary') == 'flowery']),
                    'sunburn': len([b for b in all_batches if b.get('dispensary') == 'sunburn']),
                    'trulieve': len([b for b in all_batches if b.get('dispensary') == 'trulieve']),
                    'curaleaf': len([b for b in all_batches if b.get('dispensary') == 'curaleaf']),
                    'green_dragon': len([b for b in all_batches if b.get('dispensary') == 'green_dragon'])
                },
                'batches': all_batches
            }
            
            # Save consolidated file locally (only if not in Azure Functions and not in_memory mode)
            if batch_filename and not getattr(self, 'in_memory', False):
                with open(batch_filename, 'w', encoding='utf-8') as f:
                    json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
                logger.info(f"[BATCHES] Saved consolidated batch file locally: {batch_filename}")
            
            logger.info(f"[BATCHES] Total batches: {len(all_batches)} ({len(new_batches)} new, {existing_count} existing)")
            for disp, count in consolidated_data['batches_by_dispensary'].items():
                if count > 0:
                    logger.info(f"[BATCHES]   {disp}: {count} batches")
            
            # Upload to Azure Data Lake (using same path as download)
            if self.azure_manager:
                try:
                    if hasattr(self.azure_manager, 'save_json_to_data_lake'):
                        self.azure_manager.save_json_to_data_lake(json_data=consolidated_data, file_path=azure_path, overwrite=True)
                    else:
                        file_client = self.azure_manager.file_system_client.get_file_client(azure_path)
                        file_client.upload_data(data=json.dumps(consolidated_data, ensure_ascii=False), overwrite=True)
                    
                    logger.info(f"[BATCHES] Uploaded to Azure: {azure_path}")
                except Exception as e:
                    logger.error(f"[BATCHES] CRITICAL - Failed to upload batch file to Azure: {e}", exc_info=True)
                    logger.error(f"[BATCHES] This is a critical error - batch processor will fail without batch files!")
            else:
                logger.critical(f"[BATCHES] CRITICAL - Azure Manager not initialized! Batch files will NOT be uploaded to Azure!")
            
        except Exception as e:
            logger.error(f"[BATCHES] Error in batch consolidation: {e}")
            log_exception(logger, e, context="Batch consolidation")
    
    def _print_summary(self):
        """Print final summary"""
        print()  # Empty line for console output only
        logger.info("=" * 60)
        logger.info("   FINAL SUMMARY")
        logger.info("=" * 60)
        
        summary = self.results['summary']
        
        print()  # Empty line for console output only
        logger.info(f"[*] TIMING")
        logger.info(f"    Duration: {summary['duration_seconds']:.2f} seconds")
        logger.info(f"    End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print()  # Empty line for console output only
        logger.info(f"[*] DISPENSARIES PROCESSED: {summary['successful_downloads']}/{summary['total_dispensaries']}")
        
        # Show per-dispensary details with names and file counts
        for dispensary_id, download_info in self.results.get('downloads', {}).items():
            config = self.downloaders.get(dispensary_id, {})
            name = config.get('name', dispensary_id)
            if download_info.get('success', False):
                file_count = download_info.get('files', 0)
                logger.info(f"    [OK] {name}: {file_count} files")
            else:
                error = download_info.get('error', 'Unknown error')
                logger.info(f"    [FAIL] {name}: {error}")
        
        print()  # Empty line for console output only
        logger.info(f"[*] DOWNLOAD STATISTICS")
        logger.info(f"    Total files downloaded: {summary['total_files_downloaded']}")
        logger.info(f"    Total unique batches: {summary.get('total_unique_batches', 0)}")
        logger.info(f"    Modular downloaders: {'YES' if summary['modular_downloaders_used'] else 'NO'}")
        
        print()  # Empty line for console output only
        logger.info(f"[*] AZURE UPLOAD")
        if summary['azure_upload_attempted']:
            status = "SUCCESS" if summary['azure_upload_success'] else "FAILED"
            logger.info(f"    Status: {status}")
        else:
            logger.info(f"    Status: SKIPPED")
        
        if self.results['errors']:
            print()  # Empty line for console output only
            logger.info(f"[!] ERRORS ({len(self.results['errors'])})")
            for error in self.results['errors']:
                logger.info(f"    - {error}")
        
        overall_status = "SUCCESS" if summary['overall_success'] else "FAILED"
        print()  # Empty line for console output only
        logger.info("=" * 60)
        logger.info(f"   OVERALL STATUS: {overall_status}")
        logger.info("=" * 60)
        
        if summary['overall_success']:
            print()  # Empty line for console output only
            logger.info("PIPELINE COMPLETED SUCCESSFULLY!")
            logger.info("Your dispensary data has been collected and uploaded to Azure Data Lake!")
        else:
            print()  # Empty line for console output only
            logger.info("PIPELINE COMPLETED WITH ERRORS")
            logger.info("Check the logs above for troubleshooting information.")


def print_config_and_confirm(orchestrator, args, in_memory_flag, upload_to_azure):
    """Display configuration and get user confirmation before running"""
    
    sys.stdout.write("\n" + "=" * 70 + "\n")
    sys.stdout.write("CONFIGURATION REVIEW - Please verify before running\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.flush()
    
    # Enabled dispensaries
    sys.stdout.write("\n[DISPENSARIES TO PROCESS]\n")
    enabled = [f"{cfg['name']} ({did})" for did, cfg in orchestrator.downloaders.items() if cfg.get('enabled', True)]
    for disp in enabled:
        sys.stdout.write(f"  [OK] {disp}\n")
    sys.stdout.flush()
    
    # Store counts and categories
    sys.stdout.write("\n[STORE COUNTS]\n")
    for dispensary_id, config in sorted(orchestrator.downloaders.items()):
        if not config.get('enabled', True):
            continue
        downloader = config.get('downloader')
        if downloader:
            store_count = 0
            if hasattr(downloader, 'store_ids'):
                store_count = len(downloader.store_ids) if downloader.store_ids else 0
            elif hasattr(downloader, 'location_slugs'):
                store_count = len(downloader.location_slugs) if downloader.location_slugs else 0
            
            if store_count > 0:
                sys.stdout.write(f"  {config['name']}: {store_count} stores")
                
                # Show categories if applicable (Trulieve)
                if dispensary_id == 'trulieve' and hasattr(downloader, 'category_ids') and downloader.category_ids:
                    sys.stdout.write(f" × {len(downloader.category_ids)} categories = {store_count * len(downloader.category_ids)} total requests\n")
                    sys.stdout.write(f"    Categories: {', '.join(downloader.category_ids)}\n")
                else:
                    sys.stdout.write("\n")
    sys.stdout.flush()
    
    # Processing settings
    sys.stdout.write("\n[PROCESSING MODE]\n")
    sys.stdout.write(f"  In-Memory:           {in_memory_flag}\n")
    sys.stdout.write(f"  Dev Mode:            {args.dev_mode}\n")
    sys.stdout.write(f"  Test Stores Limit:   {args.test_stores if args.test_stores > 0 else 'None (all stores)'}\n")
    sys.stdout.write(f"  Upload to Azure:     {upload_to_azure}\n")
    sys.stdout.write(f"  Dry Run:             {args.dry_run}\n")
    sys.stdout.flush()
    
    # Azure destination
    if upload_to_azure and orchestrator.azure_manager:
        sys.stdout.write("\n[AZURE DESTINATION]\n")
        sys.stdout.write(f"  Storage Account:     {AZURE_STORAGE_ACCOUNT_NAME}\n")
        sys.stdout.write(f"  Container:           {AZURE_CONTAINER_NAME}\n")
        sys.stdout.flush()
    
    sys.stdout.write("\n" + "=" * 70 + "\n")
    sys.stdout.flush()
    
    # Skip confirmation if --yes flag provided
    if hasattr(args, 'yes') and args.yes:
        sys.stdout.write("\nAuto-confirming (--yes flag provided)...\n\n")
        sys.stdout.flush()
        return True
    
    # Get confirmation
    try:
        response = input("\nProceed with this configuration? [Y/n]: ").strip().lower()
        if response and response not in ['y', 'yes']:
            sys.stdout.write("\nOperation cancelled by user.\n")
            sys.stdout.flush()
            return False
    except (KeyboardInterrupt, EOFError):
        sys.stdout.write("\n\nOperation cancelled by user.\n")
        sys.stdout.flush()
        return False
    
    sys.stdout.write("\nStarting download process...\n\n")
    sys.stdout.flush()
    return True


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Dispensary Data Orchestrator')
    parser.add_argument('--output-dir', '-o', help='Output directory for downloaded files')
    parser.add_argument('--no-parallel', action='store_true', help='(Deprecated) Dispensaries are always processed sequentially')
    parser.add_argument('--no-azure', action='store_true', help='Skip Azure upload')
    parser.add_argument('--upload-only', action='store_true', help='Upload existing files only, skip downloading')
    parser.add_argument('--dispensary', '-d', choices=['muv', 'trulieve', 'sunburn', 'cookies', 'flowery', 'curaleaf', 'green_dragon'], 
                       help='Run only specific dispensary')
    parser.add_argument('--list-dispensaries', action='store_true', help='List available dispensaries')
    parser.add_argument('--show-config', action='store_true', help='Display current configuration settings and exit')
    parser.add_argument('--download-only', action='store_true', help='Download only, skip Azure upload')
    parser.add_argument('--dev', '--dev-mode', action='store_true', dest='dev_mode',
                       help='Development mode - use only test stores for Trulieve (faster testing)')
    parser.add_argument('--in-memory', action='store_true', dest='in_memory', help='Process combined artifacts in memory and do not write batch files to disk')
    parser.add_argument('--write-local', action='store_true', dest='write_local', help='Write combined artifacts to local disk (overrides in-memory default)')
    parser.add_argument('--delete-after-upload', action='store_true', help='Delete local files after successful upload')
    parser.add_argument('--test-stores', type=int, default=0, help='Limit downloads per-dispensary to N stores for testing')
    parser.add_argument('--dry-run', action='store_true', help='Simulate uploads (no network calls, no deletions)')
    parser.add_argument('--eventhouse', action='store_true', help='Enable Event House upload (default: Data Lake only)')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompts (auto-confirm)')
    parser.add_argument('--resume', type=str, metavar='JOB_ID', help='Resume an incomplete job by its ID')
    parser.add_argument('--auto-resume', action='store_true', help='Automatically resume the most recent incomplete job if one exists')
    parser.add_argument('--jobs', action='store_true', help='List recent jobs and their status')
    parser.add_argument('--job-status', type=str, metavar='JOB_ID', help='Show detailed status of a specific job')
    
    args = parser.parse_args()

    # Default behavior: operate in-memory (do not write combined artifacts locally)
    # Use --write-local to force writing files. If --in-memory is explicitly provided, honor it.
    in_memory_flag = True
    if hasattr(args, 'write_local') and args.write_local:
        in_memory_flag = False
    elif hasattr(args, 'in_memory') and args.in_memory:
        in_memory_flag = True
    
    if args.list_dispensaries:
        logger.info("Available dispensaries:")
        orchestrator = DispensaryOrchestrator(in_memory=in_memory_flag)
        for dispensary_id, config in orchestrator.downloaders.items():
            status = "Enabled" if config.get('enabled', True) else "Disabled"
            logger.info(f"   - {config['name']} ({dispensary_id}): {status}")
        return
    
    if args.show_config:
        # Use sys.stdout.write to bypass any logging capture and show output immediately
        
        sys.stdout.write("\n" + "=" * 70 + "\n")
        sys.stdout.write("DISPENSARY ORCHESTRATOR - CURRENT CONFIGURATION\n")
        sys.stdout.write("=" * 70 + "\n")
        sys.stdout.flush()
        
        # Azure Configuration
        sys.stdout.write("\n[AZURE DATA LAKE CONFIGURATION]\n")
        sys.stdout.write(f"  Storage Account:     {AZURE_STORAGE_ACCOUNT_NAME or '(not configured)'}\n")
        sys.stdout.write(f"  Container:           {AZURE_CONTAINER_NAME or '(not configured)'}\n")
        sys.stdout.write(f"  Authentication:      {'Azure CLI' if USE_AZURE_CLI else 'Service Principal'}\n")
        if not USE_AZURE_CLI:
            sys.stdout.write(f"  Tenant ID:           {AZURE_TENANT_ID[:8] + '...' if AZURE_TENANT_ID else '(not configured)'}\n")
            sys.stdout.write(f"  Client ID:           {AZURE_CLIENT_ID[:8] + '...' if AZURE_CLIENT_ID else '(not configured)'}\n")
            sys.stdout.write(f"  Client Secret:       {'***configured***' if AZURE_CLIENT_SECRET else '(not configured)'}\n")
        sys.stdout.flush()
        
        # Event House Configuration
        sys.stdout.write("\n[EVENT HOUSE CONFIGURATION]\n")
        sys.stdout.write(f"  Cluster:             {EVENTHOUSE_CLUSTER or '(not configured)'}\n")
        sys.stdout.write(f"  Database:            {EVENTHOUSE_DATABASE or '(not configured)'}\n")
        sys.stdout.write(f"  Table:               {EVENTHOUSE_TABLE or '(not configured)'}\n")
        sys.stdout.write(f"  Column:              {EVENTHOUSE_COLUMN or '(not configured)'}\n")
        sys.stdout.flush()
        
        # Application Insights
        sys.stdout.write("\n[TELEMETRY]\n")
        app_insights_configured = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
        sys.stdout.write(f"  Application Insights: {'Configured' if app_insights_configured else 'Not configured'}\n")
        sys.stdout.flush()
        
        # Dispensary Configuration
        sys.stdout.write("\n[DISPENSARIES]\n")
        sys.stdout.flush()
        orchestrator = DispensaryOrchestrator(in_memory=in_memory_flag, dev_mode=args.dev_mode)
        
        for dispensary_id, config in sorted(orchestrator.downloaders.items()):
            status = "[YES] ENABLED" if config.get('enabled', True) else "[NO] DISABLED"
            print(f"\n  {config['name']} ({dispensary_id}): {status}")
            
            # Get store count from downloader
            downloader = config.get('downloader')
            if downloader:
                store_count = 0
                if hasattr(downloader, 'store_ids'):
                    store_count = len(downloader.store_ids) if downloader.store_ids else 0
                elif hasattr(downloader, 'location_slugs'):
                    store_count = len(downloader.location_slugs) if downloader.location_slugs else 0
                
                if store_count > 0:
                    print(f"    Stores configured:   {store_count}")
                
                # Trulieve-specific info
                if dispensary_id == 'trulieve':
                    if hasattr(downloader, 'category_ids') and downloader.category_ids:
                        print(f"    Categories:          {len(downloader.category_ids)} ({', '.join(downloader.category_ids)})")
                    if hasattr(downloader, 'store_csv_path'):
                        csv_path = getattr(downloader, 'store_csv_path', None)
                        if csv_path:
                            print(f"    Store CSV:           {os.path.basename(csv_path)}")
        
        # Processing Configuration
        print("\n[PROCESSING OPTIONS]")
        print(f"  In-Memory Mode:      {in_memory_flag}")
        print(f"  Dev Mode:            {args.dev_mode}")
        print(f"  Output Directory:    {args.output_dir or '(default: downloads/)'}")
        
        # Runtime Options
        print("\n[RUNTIME OPTIONS]")
        print(f"  Test Stores Limit:   {args.test_stores if args.test_stores > 0 else 'None (process all)'}")
        print(f"  Dry Run:             {args.dry_run}")
        print(f"  Upload to Azure:     {not (args.no_azure or args.download_only)}")
        print(f"  Download Only:       {args.download_only}")
        print(f"  Upload Only:         {args.upload_only}")
        print(f"  Delete After Upload: {args.delete_after_upload}")
        
        # Module Availability
        print("\n[MODULE AVAILABILITY]")
        print(f"  Modular Downloaders: {'[YES] Available' if MODULAR_DOWNLOADERS_AVAILABLE else '[NO] Not Available'}")
        print(f"  Job Tracking:        {'[YES] Available' if JOB_TRACKING_AVAILABLE else '[NO] Not Available'}")
        print(f"  Azure Data Lake:     {'✓ Available' if orchestrator.azure_manager else '✗ Not Available'}")
        
        print("\n" + "=" * 70 + "\n")
        return
    
    # Handle job management commands
    if args.jobs or args.job_status:
        if not JOB_TRACKING_AVAILABLE:
            logger.error("Job tracking not available. Check job_tracker.py exists.")
            sys.exit(1)
        from job_tracker import check_job_status
        check_job_status(args.job_status)
        return
    
    # Handle resume mode
    if args.resume:
        if not JOB_TRACKING_AVAILABLE:
            logger.error("Job tracking not available. Check job_tracker.py exists.")
            sys.exit(1)
        logger.info(f"[JOB] RESUME MODE - Resuming job: {args.resume}")
        
        orchestrator = DispensaryOrchestrator(args.output_dir, dev_mode=args.dev_mode, in_memory=in_memory_flag)
        orchestrator.delete_after_upload = args.delete_after_upload
        orchestrator.dry_run_upload = args.dry_run
        
        # Set the job ID on orchestrator and downloaders
        orchestrator.current_job_id = args.resume
        orchestrator._set_job_tracking_on_downloaders(args.resume)
        
        # Mark job as in_progress again
        if orchestrator.job_tracker:
            orchestrator.job_tracker.start_job(args.resume)
        
        # Run pipeline (downloaders will check for pending stores)
        results = orchestrator.run_full_pipeline(
            parallel_downloads=not args.no_parallel,
            upload_to_azure=not (args.no_azure or args.download_only)
        )
        
        flush_logs()
        sys.exit(0 if results.get('success', False) else 1)
    
    # Handle auto-resume mode - check for incomplete jobs
    if args.auto_resume and JOB_TRACKING_AVAILABLE:
        from job_tracker import JobTracker
        try:
            tracker = JobTracker(application_name="MenuDownloader")
            incomplete_jobs = tracker.get_incomplete_jobs()
            if incomplete_jobs:
                # Get the most recent incomplete job
                most_recent = incomplete_jobs[0]
                job_id = most_recent['job_id']
                pending_stores = most_recent['pending_stores']
                logger.info(f"[JOB] AUTO-RESUME: Found incomplete job {job_id} with {pending_stores} pending stores")
                logger.info(f"   Job: {most_recent['job_name']}")
                logger.info(f"   Status: {most_recent['status']}")
                logger.info(f"   Progress: {most_recent['completed_stores']}/{most_recent['total_stores']} stores completed")
                
                orchestrator = DispensaryOrchestrator(args.output_dir, dev_mode=args.dev_mode, in_memory=in_memory_flag)
                orchestrator.delete_after_upload = args.delete_after_upload
                orchestrator.dry_run_upload = args.dry_run
                orchestrator.upload_to_eventhouse = args.eventhouse
                orchestrator.current_job_id = job_id
                orchestrator._set_job_tracking_on_downloaders(job_id)
                tracker.start_job(job_id)
                
                results = orchestrator.run_full_pipeline(
                    parallel_downloads=not args.no_parallel,
                    upload_to_azure=not (args.no_azure or args.download_only)
                )
                
                flush_logs()
                sys.exit(0 if results.get('success', False) else 1)
            else:
                logger.info("[JOB] AUTO-RESUME: No incomplete jobs found, starting fresh job")
        except Exception as e:
            logger.warning(f"Could not check for incomplete jobs: {e}")
    
    # Show mode
    if args.dev_mode:
        logger.info("[DEV] DEVELOPMENT MODE - Using test stores only")
        logger.info("   Trulieve: port_orange and oakland_park only")
    
    # Create orchestrator
    orchestrator = DispensaryOrchestrator(args.output_dir, dev_mode=args.dev_mode, in_memory=in_memory_flag)
    # Attach flags to orchestrator for use during run
    orchestrator.delete_after_upload = args.delete_after_upload
    orchestrator.dry_run_upload = args.dry_run
    orchestrator.upload_to_eventhouse = args.eventhouse
    
    # Check if we have working downloaders
    if not orchestrator.downloaders:
        logger.error("No working downloaders available!")
        logger.error("Check the downloads/ directory and ensure all modules are properly installed.")
        sys.exit(1)
    
    # Filter dispensaries if specific one requested
    if args.dispensary:
        for dispensary_id in list(orchestrator.downloaders.keys()):
            if dispensary_id != args.dispensary:
                orchestrator.downloaders[dispensary_id]['enabled'] = False
        logger.info(f"Running only {args.dispensary}")
    
    # Determine if we should upload to Azure
    upload_to_azure = not (args.no_azure or args.download_only)

    # If test-stores specified, limit store_ids for downloaders that support it
    if args.test_stores and args.test_stores > 0:
        for d_id, cfg in orchestrator.downloaders.items():
            dl = cfg.get('downloader')
            if hasattr(dl, 'store_ids') and isinstance(dl.store_ids, list) and len(dl.store_ids) > args.test_stores:
                original = dl.store_ids
                dl.store_ids = dl.store_ids[:args.test_stores]
                logger.info(f"Limiting {d_id} stores from {len(original)} to {len(dl.store_ids)} for test run")
    
    # Display configuration and get confirmation (unless in upload-only or non-interactive mode or --yes flag)
    if not args.upload_only and not args.yes:
        if not print_config_and_confirm(orchestrator, args, in_memory_flag, upload_to_azure):
            logger.info("Operation cancelled by user")
            sys.exit(0)
    
    # Handle upload-only mode
    if args.upload_only:
        logger.info("UPLOAD-ONLY MODE: Uploading existing files without downloading")
        orchestrator = DispensaryOrchestrator(args.output_dir, dev_mode=args.dev_mode)
        orchestrator.upload_to_eventhouse = args.eventhouse
        upload_success = orchestrator.upload_existing_files()
        exit_code = 0 if upload_success else 1
        # Flush logs before exit
        flush_logs()
        sys.exit(exit_code)
    
    # Run the pipeline
    results = orchestrator.run_full_pipeline(
        parallel_downloads=not args.no_parallel,
        upload_to_azure=upload_to_azure
    )
    
    # Exit with appropriate code
    exit_code = 0 if results['summary']['overall_success'] else 1
    # Flush logs before exit
    flush_logs()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()



