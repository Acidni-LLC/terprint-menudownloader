import pymssql
import json
import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Get connection string from Key Vault
credential = DefaultAzureCredential()
kv_client = SecretClient("https://kv-terprint-dev.vault.azure.net", credential)
conn_str = kv_client.get_secret("terprint-sql-connection-string").value

# Parse connection string
import re
server = re.search(r'Server=tcp:([^,]+)', conn_str).group(1)
database = re.search(r'Initial Catalog=([^;]+)', conn_str).group(1)
user = re.search(r'User ID=([^;]+)', conn_str).group(1)
password = re.search(r'Password=([^;]+)', conn_str).group(1)

print(f"Connecting to {server}/{database}...")

conn = pymssql.connect(server=server, user=user, password=password, database=database)
cursor = conn.cursor(as_dict=True)

# Query for each dispensary
dispensaries = [
    (1, 'Cookies'),
    (2, 'MUV'),
    (3, 'Flowery'),
    (4, 'Trulieve'),
    (10, 'Curaleaf')
]

print("\n" + "="*100)
print("TERPRINT DATA AUDIT REPORT - Batch Records by Dispensary")
print("="*100)

for grower_id, name in dispensaries:
    print(f"\n### {name} (GrowerId={grower_id}) ###")
    
    cursor.execute("""
        SELECT TOP 3
            b.BatchName,
            b.Strain,
            b.ProductName,
            b.THC,
            b.CBD,
            b.TotalTerpenes,
            b.Myrcene,
            b.Limonene,
            b.Caryophyllene,
            b.Linalool,
            b.Pinene,
            b.CreatedDate,
            b.SourceFile
        FROM Batch b
        WHERE b.GrowerId = %s
          AND b.CreatedDate >= '2026-01-19'
        ORDER BY b.CreatedDate DESC
    """, (grower_id,))
    
    rows = cursor.fetchall()
    if rows:
        for i, row in enumerate(rows, 1):
            print(f"\n  Record {i}:")
            print(f"    Batch: {row['BatchName']}")
            print(f"    Strain: {row['Strain']}")
            print(f"    Product: {row['ProductName']}")
            print(f"    THC: {row['THC']}% | CBD: {row['CBD']}%")
            print(f"    Total Terpenes: {row['TotalTerpenes']}%")
            print(f"    Terpenes: Myrcene={row['Myrcene']}, Limonene={row['Limonene']}, Caryophyllene={row['Caryophyllene']}")
            print(f"    Created: {row['CreatedDate']}")
            print(f"    Source: {row['SourceFile']}")
    else:
        print("  No records found for date range 2026-01-19+")

conn.close()
print("\n" + "="*100)
print("Audit complete")
