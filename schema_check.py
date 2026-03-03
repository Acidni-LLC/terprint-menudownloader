import pymssql
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import re

credential = DefaultAzureCredential()
kv_client = SecretClient("https://kv-terprint-dev.vault.azure.net", credential)
conn_str = kv_client.get_secret("terprint-sql-connection-string").value

server = re.search(r'Server=tcp:([^,]+)', conn_str).group(1)
database = re.search(r'Initial Catalog=([^;]+)', conn_str).group(1)
user = re.search(r'User ID=([^;]+)', conn_str).group(1)
password = re.search(r'Password=([^;]+)', conn_str).group(1)

conn = pymssql.connect(server=server, user=user, password=password, database=database)
cursor = conn.cursor(as_dict=True)

for table in ['Strain', 'Grower', 'TerpeneValues', 'THCValues']:
    print(f"\n{table} columns:")
    cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}' ORDER BY ORDINAL_POSITION")
    for row in cursor.fetchall():
        print(f"  {row['COLUMN_NAME']} ({row['DATA_TYPE']})")

conn.close()
