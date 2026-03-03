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

# Check latest records in Batch table
print("=== LATEST BATCH RECORDS ===")
cursor.execute("""
    SELECT TOP 10
        b.BatchId,
        b.Name,
        b.created,
        g.Name as GrowerName
    FROM Batch b
    LEFT JOIN Grower g ON b.GrowerID = g.GrowerId
    ORDER BY b.created DESC
""")
for row in cursor.fetchall():
    print(f"{row['created']} | {row['GrowerName']:<15} | {row['Name'][:50]}")

print("\n=== BATCH COUNT BY DATE (Last 15 days) ===")
cursor.execute("""
    SELECT 
        CAST(created AS DATE) as ProcessDate,
        COUNT(*) as BatchCount
    FROM Batch
    GROUP BY CAST(created AS DATE)
    ORDER BY ProcessDate DESC
""")
for row in cursor.fetchall()[:15]:
    print(f"{row['ProcessDate']}: {row['BatchCount']} batches")

print("\n=== TOTAL COUNTS ===")
cursor.execute("SELECT COUNT(*) as cnt FROM Batch")
print(f"Total Batches: {cursor.fetchone()['cnt']}")
cursor.execute("SELECT COUNT(*) as cnt FROM Strain")
print(f"Total Strains: {cursor.fetchone()['cnt']}")
cursor.execute("SELECT COUNT(*) as cnt FROM TerpeneValues")
print(f"Total Terpene Records: {cursor.fetchone()['cnt']}")
cursor.execute("SELECT COUNT(*) as cnt FROM THCValues")
print(f"Total THC Records: {cursor.fetchone()['cnt']}")

conn.close()
