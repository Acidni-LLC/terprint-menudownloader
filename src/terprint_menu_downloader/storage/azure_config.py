"""
Azure Data Lake Configuration for Terprint
Update these values with your actual Azure information
"""
import os

# Try to load from terprint-config first (v4.0+)
try:
    import terprint_config
    terprint_config.load_config_to_env()
    _storage = terprint_config.get_storage_config()
    AZURE_STORAGE_ACCOUNT_NAME = _storage.get('storage_account_name', 'stterprintshared')
    AZURE_CONTAINER_NAME = _storage.get('container_name', 'jsonfiles')
    TERPRINT_CONFIG_AVAILABLE = True
except ImportError:
    TERPRINT_CONFIG_AVAILABLE = False
    # Fallback: Storage Account Information
    AZURE_STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "stterprintshared")
    AZURE_CONTAINER_NAME = os.environ.get("AZURE_CONTAINER_NAME", "jsonfiles")

# Authentication Method 1: Service Principal (Recommended for production)
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "3278dcb1-0a18-42e7-8acf-d3b5f8ae33cd")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "cbb02891-f5a1-483d-9d80-073b2519c041")
AZURE_CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET", "")  # Must be set via environment variable

# Authentication Method 2: Azure CLI (For development)
# Just run 'az login' and set USE_AZURE_CLI = True
USE_AZURE_CLI = os.environ.get("USE_AZURE_CLI", "true").lower() == "true"  # Default to Azure CLI auth

# Event House Configuration
EVENTHOUSE_CLUSTER = "trd-vdf84t56eet09mgd66.z5"      # Event House cluster name
EVENTHOUSE_DATABASE = "terprinteventhouse"             # Event House database name
EVENTHOUSE_TABLE = "onelakejsonparser"                 # Event House table name
EVENTHOUSE_COLUMN = "data"                             # Column name for JSON data
USE_EVENTHOUSE = True                                  # Use Event House instead of Data Lake

# File paths and naming conventions
BASE_PATH = "dispensaries"                                # Base folder in container
MUV_PATH = f"{BASE_PATH}/muv"                           # MÜV specific folder
INCLUDE_DATE_FOLDERS = True                              # Create YYYY/MM/DD subfolders
INCLUDE_TIMESTAMP = True                                 # Add timestamp to filenames

# Data Lake Storage Configuration
BLOB_TYPE = "BlockBlob"                                 # Block blob for JSON files
CONTENT_TYPE = "application/json"                       # Content type for uploads
OVERWRITE = True                                        # Overwrite existing files
TIMEOUT = 300                                          # Upload timeout in seconds

# Logging Configuration
LOG_LEVEL = "INFO"                                      # DEBUG, INFO, WARNING, ERROR
LOG_FILE = "azure_datalake.log"                       # Log file name (optional)

# Retry Configuration
MAX_RETRIES = 3                                        # Maximum retry attempts
RETRY_DELAY = 5                                        # Delay between retries (seconds)

# Application Insights Configuration (use environment variable)
import os
APPLICATIONINSIGHTS_CONNECTION_STRING = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING', '')

# File Organization Settings
DATE_FORMAT = "%Y/%m/%d"                               # Date folder format
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"                     # Timestamp format for files
FILE_EXTENSION = ".json"                               # Default file extension

# Environment-specific settings
ENVIRONMENT = "development"  # development, staging, production

# Optional: Environment-specific overrides
if ENVIRONMENT == "production":
    LOG_LEVEL = "WARNING"
    OVERWRITE = False  # Be more careful in production
elif ENVIRONMENT == "development":
    LOG_LEVEL = "DEBUG"
    INCLUDE_DATE_FOLDERS = False  # Simpler structure for dev

# Validation function
def validate_config():
    """
    Validate configuration settings
    Returns True if valid, False otherwise
    """
    errors = []
    
    # Check required fields
    if AZURE_STORAGE_ACCOUNT_NAME == "your-storage-account-name":
        errors.append("AZURE_STORAGE_ACCOUNT_NAME must be updated")
    
    if AZURE_CONTAINER_NAME == "your-container-name":
        errors.append("AZURE_CONTAINER_NAME must be updated")
    
    if not USE_AZURE_CLI:
        if AZURE_CLIENT_ID == "your-client-id":
            errors.append("AZURE_CLIENT_ID must be updated when using Service Principal")
        
        if AZURE_CLIENT_SECRET == "your-client-secret":
            errors.append("AZURE_CLIENT_SECRET must be updated when using Service Principal")
    
    # Check Event House settings if using Event House
    if USE_EVENTHOUSE:
        if EVENTHOUSE_CLUSTER == "your-cluster-name":
            errors.append("EVENTHOUSE_CLUSTER must be updated when using Event House")
        
        if EVENTHOUSE_DATABASE == "your-database-name":
            errors.append("EVENTHOUSE_DATABASE must be updated when using Event House")
        
        if EVENTHOUSE_TABLE == "your-table-name":
            errors.append("EVENTHOUSE_TABLE must be updated when using Event House")
        
        if not USE_AZURE_CLI:
            if AZURE_TENANT_ID == "your-tenant-id":
                errors.append("AZURE_TENANT_ID must be updated when using Event House with Service Principal")
    
    # Check format validity
    try:
        from datetime import datetime
        datetime.now().strftime(DATE_FORMAT)
        datetime.now().strftime(TIMESTAMP_FORMAT)
    except ValueError as e:
        errors.append(f"Invalid date/timestamp format: {e}")
    
    if errors:
        print("❌ Configuration errors found:")
        for error in errors:
            print(f"   • {error}")
        return False
    
    print("✅ Configuration is valid")
    return True

# Helper function to get full paths
def get_file_path(filename, subfolder="", include_date=None, include_timestamp=None):
    """
    Generate full file path based on configuration
    
    Args:
        filename (str): Base filename
        subfolder (str): Optional subfolder (e.g., 'muv', 'trulieve')
        include_date (bool): Override INCLUDE_DATE_FOLDERS
        include_timestamp (bool): Override INCLUDE_TIMESTAMP
    
    Returns:
        str: Full file path
    """
    from datetime import datetime
    
    # Use config defaults if not specified
    if include_date is None:
        include_date = INCLUDE_DATE_FOLDERS
    if include_timestamp is None:
        include_timestamp = INCLUDE_TIMESTAMP
    
    path_parts = []
    
    # Add base path
    if BASE_PATH:
        path_parts.append(BASE_PATH)
    
    # Add subfolder
    if subfolder:
        path_parts.append(subfolder)
    
    # Add date folder
    if include_date:
        date_folder = datetime.now().strftime(DATE_FORMAT)
        path_parts.append(date_folder)
    
    # Build filename
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    
    if include_timestamp:
        timestamp = datetime.now().strftime(TIMESTAMP_FORMAT)
        final_filename = f"{name}_{timestamp}"
    else:
        final_filename = name
    
    # Add extension
    if ext:
        final_filename += f".{ext}"
    elif not final_filename.endswith(FILE_EXTENSION):
        final_filename += FILE_EXTENSION
    
    # Combine all parts
    if path_parts:
        return "/".join(path_parts) + "/" + final_filename
    else:
        return final_filename

# Print current configuration
def print_config():
    """Print current configuration (without secrets)"""
    print("📋 AZURE DATA LAKE CONFIGURATION")
    print("="*50)
    print(f"Storage Account: {AZURE_STORAGE_ACCOUNT_NAME}")
    print(f"Container: {AZURE_CONTAINER_NAME}")
    print(f"Tenant ID: {AZURE_TENANT_ID}")
    print(f"Auth Method: {'Azure CLI' if USE_AZURE_CLI else 'Service Principal'}")
    if not USE_AZURE_CLI:
        print(f"Client ID: {AZURE_CLIENT_ID}")
        print(f"Client Secret: {'*' * len(AZURE_CLIENT_SECRET) if AZURE_CLIENT_SECRET != 'your-client-secret' else 'NOT SET'}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Base Path: {BASE_PATH}")
    print(f"Date Folders: {INCLUDE_DATE_FOLDERS}")
    print(f"Timestamps: {INCLUDE_TIMESTAMP}")
    print(f"Log Level: {LOG_LEVEL}")
    print()
    
    # Show example paths
    print("📁 EXAMPLE FILE PATHS:")
    print(f"MÜV Products: {get_file_path('muv_products.json', 'muv')}")
    print(f"Trulieve Menu: {get_file_path('trulieve_menu.json', 'trulieve')}")
    print(f"Simple File: {get_file_path('test.json', include_date=False, include_timestamp=False)}")
    print()

if __name__ == "__main__":
    print_config()
    validate_config()
