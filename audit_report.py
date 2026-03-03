import pymssql
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import re
from datetime import datetime

credential = DefaultAzureCredential()
kv_client = SecretClient("https://kv-terprint-dev.vault.azure.net", credential)
conn_str = kv_client.get_secret("terprint-sql-connection-string").value

server = re.search(r'Server=tcp:([^,]+)', conn_str).group(1)
database = re.search(r'Initial Catalog=([^;]+)', conn_str).group(1)
user = re.search(r'User ID=([^;]+)', conn_str).group(1)
password = re.search(r'Password=([^;]+)', conn_str).group(1)

conn = pymssql.connect(server=server, user=user, password=password, database=database)
cursor = conn.cursor(as_dict=True)

print("="*120)
print(f"TERPRINT DATA AUDIT REPORT")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Date Range: 2026-01-19 onwards (backfilled data)")
print("="*120)

# Get Grower list
cursor.execute("SELECT GrowerId, Name FROM Grower ORDER BY GrowerId")
growers = cursor.fetchall()
print(f"\nDispensaries/Growers in system: {len(growers)}")
for g in growers:
    print(f"  {g['GrowerId']}: {g['Name']}")

# Audit each grower
for grower in growers:
    grower_id = grower['GrowerId']
    grower_name = grower['Name']
    
    print(f"\n{'='*120}")
    print(f"### {grower_name} (GrowerId={grower_id}) ###")
    print("="*120)
    
    # Get recent batches
    cursor.execute("""
        SELECT TOP 3
            b.BatchId,
            b.Name as BatchName,
            b.Type as ProductType,
            s.StrainName,
            b.totalTerpenes,
            b.totalCannabinoids,
            b.StoreName,
            b.created,
            b.Date
        FROM Batch b
        LEFT JOIN Strain s ON b.StrainID = s.StrainId
        WHERE b.GrowerID = %s
          AND b.created >= '2026-01-19'
        ORDER BY b.created DESC
    """, (grower_id,))
    
    batches = cursor.fetchall()
    
    if not batches:
        print("    No records found for date range 2026-01-19+")
        continue
    
    print(f"  Found {len(batches)} recent batches")
    
    for batch in batches:
        batch_id = batch['BatchId']
        print(f"\n   BATCH: {batch['BatchName']}")
        print(f"    Strain: {batch['StrainName']}")
        print(f"    Product Type: {batch['ProductType']}")
        print(f"    Store: {batch['StoreName']}")
        print(f"    Total Terpenes: {batch['totalTerpenes']}")
        print(f"    Total Cannabinoids: {batch['totalCannabinoids']}")
        print(f"    Created: {batch['created']}")
        
        # Get terpene values
        cursor.execute("""
            SELECT TerpeneName, Value, Scale
            FROM TerpeneValues 
            WHERE BatchID = %s
            ORDER BY Value DESC
        """, (batch_id,))
        terpenes = cursor.fetchall()
        
        if terpenes:
            print(f"  ")
            print(f"     TERPENES ({len(terpenes)} compounds):")
            for t in terpenes[:5]:  # Show top 5
                val = t['Value'] if t['Value'] else 0
                print(f"        {t['TerpeneName']}: {val:.4f}% ({t['Scale']})")
            if len(terpenes) > 5:
                print(f"       ... and {len(terpenes)-5} more")
        
        # Get THC/cannabinoid values
        cursor.execute("""
            SELECT Analyte, Percent, Result
            FROM THCValues 
            WHERE BatchID = %s
            ORDER BY Percent DESC
        """, (batch_id,))
        thc_values = cursor.fetchall()
        
        if thc_values:
            print(f"  ")
            print(f"     CANNABINOIDS ({len(thc_values)} compounds):")
            for t in thc_values[:5]:  # Show top 5
                pct = t['Percent'] if t['Percent'] else 0
                print(f"        {t['Analyte']}: {pct:.2f}%")
            if len(thc_values) > 5:
                print(f"       ... and {len(thc_values)-5} more")
        
        print(f"  ")

# Summary stats
print(f"\n{'='*120}")
print("SUMMARY STATISTICS")
print("="*120)

cursor.execute("""
    SELECT 
        g.Name as GrowerName,
        COUNT(b.BatchId) as TotalBatches,
        COUNT(DISTINCT s.StrainId) as UniqueStrains,
        MIN(b.created) as FirstRecord,
        MAX(b.created) as LastRecord
    FROM Batch b
    JOIN Grower g ON b.GrowerID = g.GrowerId
    LEFT JOIN Strain s ON b.StrainID = s.StrainId
    WHERE b.created >= '2026-01-19'
    GROUP BY g.Name, g.GrowerId
    ORDER BY TotalBatches DESC
""")

print("\nRecords by Dispensary (since 2026-01-19):")
print(f"{'Dispensary':<20} {'Batches':>10} {'Strains':>10} {'First Record':<22} {'Last Record':<22}")
print("-"*90)
for row in cursor.fetchall():
    print(f"{row['GrowerName']:<20} {row['TotalBatches']:>10} {row['UniqueStrains']:>10} {str(row['FirstRecord']):<22} {str(row['LastRecord']):<22}")

conn.close()
print(f"\n{'='*120}")
print("Audit Complete")
print("="*120)
