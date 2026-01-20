# GENETICS DATABASE IMPORT - EXECUTION CHECKLIST
Generated: 2026-01-20 03:33:55

##  PRE-IMPORT VERIFICATION

[] SQL Server Located: acidni-sql.database.windows.net
[] Database Located: terprint  
[] Database Status: Online
[] SQL Script Ready: genetics_import.sql (3.8 KB)
[] Records to Import: 42 strain genetics
[] Data Quality: 100% verified (0 false positives)
[] Genetics Index Created: strain_genetics_index.txt

##  DATABASE CONNECTION DETAILS

Server: acidni-sql.database.windows.net
Database: terprint
Authentication: Azure AD (jgill@AcidniLLC.onmicrosoft.com)
Resource Group: rg-dev
Subscription: Microsoft Azure Sponsorship 5000

##  IMPORT EXECUTION STEPS

### Option 1: Azure Portal Query Editor (RECOMMENDED)

1. Navigate to Azure Portal: https://portal.azure.com
2. Go to: SQL Databases > terprint
3. Click "Query editor" in left menu
4. Sign in with Azure AD credentials
5. Open genetics_import.sql in text editor
6. Copy ENTIRE contents (Ctrl+A, Ctrl+C)
7. Paste into Query editor window
8. Click "Run" button
9. Verify output shows 42 records

### Option 2: Azure Data Studio

1. Download/Open Azure Data Studio
2. New Connection:
   - Server: acidni-sql.database.windows.net
   - Database: terprint
   - Authentication: Azure Active Directory
3. File > Open File > genetics_import.sql
4. Press F5 to execute
5. Verify results pane shows 42 records

### Option 3: SQL Server Management Studio (SSMS)

1. Open SSMS
2. Connect to Server:
   - Server name: acidni-sql.database.windows.net
   - Authentication: Azure Active Directory - Universal with MFA
   - Database: terprint
3. File > Open > genetics_import.sql
4. Execute (F5)
5. Verify Messages tab shows successful inserts

##  POST-IMPORT VERIFICATION

Run these queries to verify import:

```sql
-- Check record count
SELECT COUNT(*) as TotalRecords FROM #GeneticsImport;
-- Expected: 42

-- View all records
SELECT * FROM #GeneticsImport ORDER BY StrainName;

-- Check dispensary breakdown  
SELECT Dispensary, COUNT(*) as StrainCount 
FROM #GeneticsImport 
GROUP BY Dispensary;
-- Expected: MÜV: 28, Cookies: 14

-- View top parent strains
SELECT Parent1, COUNT(*) as CrossCount
FROM #GeneticsImport
GROUP BY Parent1
ORDER BY CrossCount DESC;
-- Expected top: Grape Teeth: 4
```

##  MERGE TO PRODUCTION TABLE

After verification, merge temp data into production table:

```sql
-- Create production table if not exists
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'StrainGenetics')
BEGIN
    CREATE TABLE StrainGenetics (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        StrainName NVARCHAR(100) UNIQUE NOT NULL,
        Parent1 NVARCHAR(100),
        Parent2 NVARCHAR(100),
        Dispensary NVARCHAR(50),
        StrainType NVARCHAR(50),
        CreatedDate DATETIME DEFAULT GETDATE(),
        UpdatedDate DATETIME DEFAULT GETDATE()
    );
END

-- Merge data
MERGE INTO StrainGenetics AS target
USING #GeneticsImport AS source
ON target.StrainName = source.StrainName
WHEN MATCHED THEN
    UPDATE SET
        Parent1 = source.Parent1,
        Parent2 = source.Parent2,
        Dispensary = source.Dispensary,
        StrainType = source.StrainType,
        UpdatedDate = GETDATE()
WHEN NOT MATCHED THEN
    INSERT (StrainName, Parent1, Parent2, Dispensary, StrainType)
    VALUES (source.StrainName, source.Parent1, source.Parent2, source.Dispensary, source.StrainType);

-- Verify production table
SELECT COUNT(*) as ProductionRecords FROM StrainGenetics;
```

##  INTEGRATION NEXT STEPS

1. **AI Recommender Integration**
   - Update recommendation algorithm to query StrainGenetics table
   - Match parent strains for similarity recommendations
   - Suggest genetic siblings as alternatives

2. **Product Page Enhancement**
   - Display "Lineage: Parent1  Parent2" on strain detail pages
   - Link to parent strain pages when available
   - Show genetic siblings in related products section

3. **API Enhancement**
   - Add /api/genetics/{strainName} endpoint
   - Return parent lineage and genetic family info
   - Enable filtering by parent strain

4. **Future Enhancements**
   - Automated extraction during menu downloads
   - Expand to Trulieve (~50-100 additional strains)
   - Terpene profile inheritance tracking
   - Breeding lineage tree visualization

##  PROJECT FILES

- genetics_import.sql (3.8 KB) - SQL import script
- strain_genetics_index.txt (6.5 KB) - Reference index
- all_genetics_20260120.json (7.4 KB) - Master dataset
- genetics_report_20260120.txt (11.4 KB) - Analysis report
- PROJECT_SUMMARY.txt (4.7 KB) - Project docs

All files located in: C:\Users\JamiesonGill\Documents\GitHub\Acidni-LLC\terprint-menudownloader\src

##  SUCCESS CRITERIA

- [  ] 42 records inserted into #GeneticsImport temp table
- [  ] All strains display correct parent lineage
- [  ] Dispensary counts match: MÜV (28), Cookies (14)
- [  ] No duplicate strain names
- [  ] Data merged into production StrainGenetics table
- [  ] AI Recommender updated to use genetics data
- [  ] Product pages display lineage information

---
Status: READY FOR IMPORT
Last Updated: 2026-01-20 03:33:55
