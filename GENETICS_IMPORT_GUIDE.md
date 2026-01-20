# Terprint Genetics Import Guide

##  Summary

**Total Genetics Ready for Import: 63 unique strains**

- Original Menu JSON Extraction: 42 strains
- Menu Description Parsing: 45 genetics (MÜV: 31, Cookies: 14)
- **Deduplicated Total: 63 unique strains**

##  Files Generated

| File | Location | Purpose |
|------|----------|---------|
| `FINAL_CONSOLIDATED_GENETICS.json` | `src/` | Complete genetics dataset (JSON) |
| `FINAL_GENETICS_IMPORT.sql` | `src/` | Ready-to-execute SQL import script |
| `FINAL_CONSOLIDATED_GENETICS.json` | Azure: `jsonfiles/genetics/combined/` | Backup in Azure Storage |
| `FINAL_GENETICS_IMPORT.sql` | Azure: `jsonfiles/genetics/combined/` | Backup in Azure Storage |

##  Database Import Instructions

### Option 1: Azure Portal (Recommended)

1. Open [Azure Portal](https://portal.azure.com)
2. Navigate to: **acidni-sql > terprint database > Query editor (preview)**
3. Authenticate with Azure AD
4. Open `src/FINAL_GENETICS_IMPORT.sql`
5. Copy and paste the entire SQL script
6. Click **Run**
7. Verify with:
   ```sql
   SELECT COUNT(*) AS TotalGenetics FROM Genetics;
   SELECT Source, COUNT(*) AS Count FROM Genetics GROUP BY Source ORDER BY Count DESC;
   SELECT TOP 20 StrainName, Parent1, Parent2, Dispensary FROM Genetics ORDER BY StrainName;
   ```

Expected result: **63 rows** inserted

### Option 2: Azure Data Studio / SSMS

```bash
# Download Azure Data Studio
https://aka.ms/azuredatastudio

# Connect to:
Server: acidni-sql.database.windows.net
Database: terprint
Authentication: Azure Active Directory

# Run FINAL_GENETICS_IMPORT.sql
```

##  What Was Extracted

### Successful Extraction Methods

#### 1. Menu JSON Extraction (42 strains)
- **Source**: Menu JSON files from all dispensaries
- **Method**: Parse product objects directly from API responses
- **Quality**: Medium confidence (some may lack parent info)

#### 2. Menu Description Parsing (45 genetics)
- **Source**: Product descriptions in menu JSON files
- **Dispensaries**: MÜV (31), Cookies (14)
- **Method**: Regex pattern matching for genetics phrases:
  - "cross of X and Y"
  - "X x Y"
  - "hybrid of X and Y"
  - "blend of X and Y"
- **Quality**: High confidence (explicitly stated in descriptions)

### Unsuccessful Attempts

 **Web Scraping Product Pages**
- Issue: 404 errors, rate limiting
- Reason: Menu APIs return shopping data, not informational pages

 **COA PDF Parsing**
- Issue: `lab_test_url` field is `null` in all Curaleaf products
- Future: Implement PDF parsing when COAs become available

 **Curaleaf/Flowery/Trulieve Descriptions**
- Issue: No genetics information in product descriptions

##  Sample Genetics Data

```
Apple MAC = MAC 1 x Trophy Wife
Apples & Bananas = Platinum Cookies x Granddaddy Purple
Black Amber = GMO x OZ Kush Bx2
Blue Raz = Yadada x E85
E85 = Wedding Cake x Project 4516
GG #4 = Chocolate Diesel x Chemdawg 91 X Sour Diesel
Gelato = Sunset Sherbet x Thin Mint Cookies
Ice Cream Cake = Gelato 33 x Wedding Cake
Triangle Kush = Hindu Kush x Lemon Thai
```

##  Automated Updates

### Weekly Menu Description Scan

Run this script weekly to catch new genetics:

```bash
cd src
python menu_description_genetics.py
```

This will scan the last 30 days of menu files and extract any new genetics from product descriptions.

##  Integration Points

### 1. AI Recommender Enhancement
- Use genetics for "similar strain" recommendations
- Show parent strains on product pages
- Filter by genetic lineage

### 2. Product Pages
Display genetics info:
```
Strain: Blue Dream
Genetics: Blueberry x Haze
Type: Hybrid (Sativa-dominant)
```

### 3. Search & Filtering
- Search by parent strain
- "Show me all strains descended from OG Kush"
- Lineage explorer / family tree visualization

##  Future Enhancements

1. **Leafly/AllBud Scraping** (~100-200 more strains)
2. **COA PDF Parsing** (when lab_test_url becomes available)
3. **Manual Curation** (top 50 popular strains)
4. **Community Contribution** (verified user submissions)
5. **API Integration** (Seedfinder, Strain API, etc.)

##  Important Notes

- **Duplicate Prevention**: SQL script uses `WHERE NOT EXISTS` to prevent duplicates
- **Unique Constraint**: `StrainName` has a unique constraint in the table
- **Idempotent**: Safe to run import script multiple times
- **Encoding**: Files are UTF-8 encoded (handles special characters)

##  Support

If you encounter issues:
1. Check Azure Portal Query Editor for detailed error messages
2. Verify database connection and permissions
3. Review SQL script for syntax errors
4. Check `StrainName` uniqueness constraints

---

**Generated**: 2026-01-20  
**Total Genetics**: 63 unique strains  
**Status**:  Ready for Import
