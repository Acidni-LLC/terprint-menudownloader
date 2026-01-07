import json
import os
from datetime import datetime
from azure.storage.filedatalake import DataLakeServiceClient, ContentSettings
from azure.identity import DefaultAzureCredential, ClientSecretCredential, AzureCliCredential
import logging

class AzureDataLakeManager:
    def __init__(self, account_name, container_name, credential=None):
        """
        Initialize Azure Data Lake connection
        
        Args:
            account_name (str): Storage account name
            container_name (str): Container/filesystem name
            credential: Azure credential (optional, uses AzureCliCredential for local dev)
        """
        self.account_name = account_name
        self.container_name = container_name
        self.account_url = f"https://{account_name}.dfs.core.windows.net"
        
        # Batch extraction callback
        self.batch_callback = None
        
        # Set up credential - use DefaultAzureCredential for Azure environments, AzureCliCredential for local dev
        if credential is None:
            # Detect Azure environment (Functions, Container Apps, App Service)
            is_azure_environment = (
                os.environ.get('FUNCTIONS_WORKER_RUNTIME') is not None or  # Azure Functions
                os.environ.get('CONTAINER_APP_NAME') is not None or        # Azure Container Apps
                os.environ.get('WEBSITE_SITE_NAME') is not None or         # Azure App Service
                os.environ.get('IDENTITY_ENDPOINT') is not None            # Managed Identity available
            )
            if is_azure_environment:
                self.credential = DefaultAzureCredential()
            else:
                # Use AzureCliCredential for local development (more reliable with RBAC)
                self.credential = AzureCliCredential()
        else:
            self.credential = credential
            
        # Initialize Data Lake Service Client with compatible API version
        self.service_client = DataLakeServiceClient(
            account_url=self.account_url,
            credential=self.credential,
            api_version="2024-11-04"  # Latest supported version by azure-storage-blob 12.23.0
        )
        
        # Get filesystem client
        self.file_system_client = self.service_client.get_file_system_client(
            file_system=self.container_name
        )
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def get_container_info(self):
        """
        Get container/filesystem information to test connection
        
        Returns:
            dict: Container properties or None if failed
        """
        try:
            properties = self.file_system_client.get_file_system_properties()
            return {
                'name': self.container_name,
                'account': self.account_name,
                'last_modified': properties.last_modified,
                'etag': properties.etag
            }
        except Exception as e:
            self.logger.error(f"Error getting container info: {str(e)}")
            return None

    def ensure_directory_exists(self, directory_path):
        """
        Ensure a directory path exists in the data lake
        
        Args:
            directory_path (str): Directory path to create
            
        Returns:
            bool: True if directory exists/was created
        """
        try:
            if not directory_path:
                return True
                
            directory_client = self.file_system_client.get_directory_client(directory_path)
            
            # Try to get properties first to see if it exists
            try:
                directory_client.get_directory_properties()
                self.logger.info(f"Directory already exists: {directory_path}")
                return True
            except:
                # Directory doesn't exist, create it
                directory_client.create_directory()
                self.logger.info(f"Created directory: {directory_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error ensuring directory exists: {str(e)}")
            return False

    def set_content_properties(self, file_path, content_type):
        """
        Set content properties for a file
        
        Args:
            file_path (str): Path to the file
            content_type (str): MIME content type (e.g., 'application/json')
            
        Returns:
            bool: Success status
        """
        try:
            file_client = self.file_system_client.get_file_client(file_path)
            
            # Set content settings
            content_settings = ContentSettings(content_type=content_type)
            file_client.set_http_headers(content_settings=content_settings)
            
            self.logger.info(f"Set content type '{content_type}' for: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting content properties: {str(e)}")
            return False

    def save_json_to_data_lake(self, json_data, file_path, overwrite=True):
        """
        Save JSON data to Azure Data Lake
        
        Args:
            json_data: Dictionary or JSON string to save
            file_path (str): Path in data lake (e.g., 'folder/filename.json')
            overwrite (bool): Whether to overwrite existing file
            
        Returns:
            bool: Success status
        """
        try:
            # Convert to JSON string if it's a dictionary
            if isinstance(json_data, dict):
                json_string = json.dumps(json_data, indent=2, ensure_ascii=False)
            else:
                json_string = str(json_data)
            
            # Call batch extraction callback before saving (if set)
            if self.batch_callback and isinstance(json_data, dict):
                try:
                    self.batch_callback(file_path, json_data)
                except Exception as cb_error:
                    self.logger.warning(f"Batch callback error: {cb_error}")
            
            # Get file client
            file_client = self.file_system_client.get_file_client(file_path)
            
            # Upload the file
            file_client.upload_data(
                data=json_string,
                overwrite=overwrite
            )
            
            self.logger.info(f"Successfully saved JSON to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving JSON to Data Lake: {str(e)}")
            return False

    def save_json_file_to_data_lake(self, local_file_path, remote_file_path, overwrite=True):
        """
        Upload a local JSON file to Azure Data Lake
        
        Args:
            local_file_path (str): Path to local JSON file
            remote_file_path (str): Destination path in data lake
            overwrite (bool): Whether to overwrite existing file
            
        Returns:
            bool: Success status
        """
        try:
            if not os.path.exists(local_file_path):
                self.logger.error(f"Local file not found: {local_file_path}")
                return False
            
            # Read the JSON file
            with open(local_file_path, 'r', encoding='utf-8') as file:
                json_data = file.read()
            
            # Get file client
            file_client = self.file_system_client.get_file_client(remote_file_path)
            
            # Upload the file
            file_client.upload_data(
                data=json_data,
                overwrite=overwrite
            )
            
            self.logger.info(f"Successfully uploaded {local_file_path} to: {remote_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error uploading file to Data Lake: {str(e)}")
            return False

    def save_json_with_timestamp(self, json_data, base_path, include_date_folder=True):
        """
        Save JSON with timestamp in filename
        
        Args:
            json_data: JSON data to save
            base_path (str): Base path (e.g., 'muv_products')
            include_date_folder (bool): Whether to create date-based folders
            
        Returns:
            str: Full path where file was saved, or None if failed
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if include_date_folder:
                date_folder = datetime.now().strftime("%Y/%m/%d")
                file_path = f"{base_path}/{date_folder}/{base_path}_{timestamp}.json"
            else:
                file_path = f"{base_path}_{timestamp}.json"
            
            success = self.save_json_to_data_lake(json_data, file_path)
            
            if success:
                return file_path
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error saving timestamped JSON: {str(e)}")
            return None

    def list_files(self, directory_path=""):
        """
        List files in a directory in Data Lake
        
        Args:
            directory_path (str): Directory path to list
            
        Returns:
            list: List of file names
        """
        try:
            # Handle empty directory path
            if not directory_path:
                paths = self.file_system_client.get_paths()
            else:
                # Check if directory exists first
                try:
                    directory_client = self.file_system_client.get_directory_client(directory_path)
                    directory_client.get_directory_properties()
                    paths = self.file_system_client.get_paths(path=directory_path)
                except:
                    # Directory doesn't exist
                    self.logger.warning(f"Directory not found: {directory_path}")
                    return []
            
            files = [path.name for path in paths if not path.is_directory]
            return files
            
        except Exception as e:
            self.logger.error(f"Error listing files: {str(e)}")
            return []

    def file_exists(self, file_path):
        """
        Check if file exists in Data Lake
        
        Args:
            file_path (str): Path to check
            
        Returns:
            bool: True if file exists
        """
        try:
            file_client = self.file_system_client.get_file_client(file_path)
            file_client.get_file_properties()
            return True
        except:
            return False

# Configuration and usage functions
def get_credential_from_service_principal(tenant_id, client_id, client_secret):
    """
    Create credential using service principal
    
    Args:
        tenant_id (str): Azure tenant ID
        client_id (str): Application (client) ID
        client_secret (str): Client secret
        
    Returns:
        ClientSecretCredential: Azure credential
    """
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )

def save_muv_products_to_data_lake(json_file_path=None, json_data=None):
    """
    Specific function to save MÜV products JSON to Data Lake
    
    Args:
        json_file_path (str): Path to local JSON file (optional)
        json_data (dict): JSON data dictionary (optional)
    """
    # Configuration - update these values
    STORAGE_ACCOUNT_NAME = "your_storage_account_name"
    CONTAINER_NAME = "your_container_name"
    
    # Option 1: Use environment variables for credentials
    # os.environ["AZURE_TENANT_ID"] = "your_tenant_id"
    # os.environ["AZURE_CLIENT_ID"] = "your_client_id"
    # os.environ["AZURE_CLIENT_SECRET"] = "your_client_secret"
    
    # Option 2: Use service principal directly
    # credential = get_credential_from_service_principal(
    #     tenant_id="your_tenant_id",
    #     client_id="your_client_id",
    #     client_secret="your_client_secret"
    # )
    
    try:
        # Initialize Data Lake manager
        dl_manager = AzureDataLakeManager(
            account_name=STORAGE_ACCOUNT_NAME,
            container_name=CONTAINER_NAME
            # credential=credential  # Uncomment if using service principal
        )
        
        if json_file_path:
            # Save from file
            remote_path = dl_manager.save_json_with_timestamp(
                json_data=None, 
                base_path="muv_products"
            )
            
            if remote_path:
                success = dl_manager.save_json_file_to_data_lake(
                    local_file_path=json_file_path,
                    remote_file_path=remote_path
                )
            else:
                success = False
                
        elif json_data:
            # Save from dictionary
            remote_path = dl_manager.save_json_with_timestamp(
                json_data=json_data,
                base_path="muv_products"
            )
            success = remote_path is not None
        else:
            print("Either json_file_path or json_data must be provided")
            return False
        
        if success:
            print(f"Successfully saved to Data Lake: {remote_path}")
            return True
        else:
            print("Failed to save to Data Lake")
            return False
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

# Example usage
if __name__ == "__main__":
    # Example 1: Save local JSON file
    local_json_path = r"C:\Users\JamiesonGill\source\repos\Acidni-LLC\Terprint\muv_products.json"
    save_muv_products_to_data_lake(json_file_path=local_json_path)
    
    # Example 2: Save JSON data directly
    sample_data = {
        "timestamp": datetime.now().isoformat(),
        "source": "MUV API",
        "data": {"products": []}
    }
    save_muv_products_to_data_lake(json_data=sample_data)
    
    # Example 3: Advanced usage
    STORAGE_ACCOUNT = "your_account"
    CONTAINER = "your_container"
    
    dl_manager = AzureDataLakeManager(STORAGE_ACCOUNT, CONTAINER)
    
    # Save with custom path
    success = dl_manager.save_json_to_data_lake(
        json_data=sample_data,
        file_path="dispensaries/muv/products/latest.json"
    )
    
    # List files
    files = dl_manager.list_files("dispensaries/muv/products/")
    print("Files in directory:", files)

def setup_azure_environment():
    """
    Set up Azure environment variables
    """
    # Update these with your actual values
    os.environ["AZURE_TENANT_ID"] = "your-tenant-id"
    os.environ["AZURE_CLIENT_ID"] = "your-client-id"
    os.environ["AZURE_CLIENT_SECRET"] = "your-client-secret"
    os.environ["AZURE_STORAGE_ACCOUNT"] = "your-storage-account"
    os.environ["AZURE_CONTAINER_NAME"] = "your-container"
    
    print("Azure environment variables set")

if __name__ == "__main__":
    setup_azure_environment()
