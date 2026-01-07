# Deployment & Activation Guide

## Phase 1: Deploy Updated Azure Function (v1.3.3)

### Step 1: Publish to Azure
```powershell
# From azure_function directory
cd azure_function

# Ensure v1.3.3 is in requirements.txt
cat requirements.txt  # Should show: terprint-menu-downloader>=1.3.3

# Deploy to Azure
func azure functionapp publish terprint-menu-downloader --build remote
```

**Expected Output**:
```
...
Installing specified packages in .venv as per requirements.txt using pip, when --skip-pip-packages is not specified.
...
terprint-menu-downloader (1.3.3)
...
Deployment successful!
```

### Step 2: Verify Deployment
```powershell
# Check Azure Function logs
az functionapp log tail --name terprint-menu-downloader --resource-group rg-dev-terprint-menudownloader

# Test health endpoint
curl https://terprint-menu-downloader.azurewebsites.net/api/health/batches
curl https://terprint-menu-downloader.azurewebsites.net/api/health/diagnostics
```

---

## Phase 2: Manual Trigger & Validation

### Step 1: Manually Trigger Batch Processing
```powershell
# Trigger the orchestration manually
curl -X POST https://terprint-menu-downloader.azurewebsites.net/api/run

# Expected Response:
# {"status": "orchestration_started", "instance_id": "..."}
```

### Step 2: Monitor Execution
```powershell
# Check Azure Data Lake for new batch files
az storage blob list \
  --account-name terprintstorage8643 \
  --container-name menus \
  --prefix batches/ \
  --output table

# Expected: New file like `consolidated_batches_20250113.json`
```

### Step 3: Check Application Insights Logs
```kusto
// In Application Insights -> Logs
traces
| where message contains "[BATCHES]"
| order by timestamp desc
| take 50
| project timestamp, message, severityLevel
```

**Expected Output**:
- INFO: `[BATCHES] Starting batch consolidation. Batch tracker has X batches`
- INFO: `[BATCHES] Batch consolidation completed in X seconds`
- INFO: `[BATCHES] Azure upload successful. Uploaded consolidated batch file.`

---

## Phase 3: Timer Trigger Activation

### Step 1: Restart Azure Function App
```powershell
# This resets the timer trigger runtime
az functionapp restart \
  --name terprint-menu-downloader \
  --resource-group rg-dev-terprint-menudownloader
```

### Step 2: Monitor Next Scheduled Trigger
**Timer Schedule**: `0 0 2,14,20 * * *`
- 02:00 UTC (10 PM EST) ← First trigger tonight
- 14:00 UTC (10 AM EST) ← Next morning
- 20:00 UTC (4 PM EST) ← Afternoon

### Step 3: Verify Timer Trigger Fired
```kusto
// In Application Insights -> Logs
traces
| where message contains "scheduled_menu_download"
| where timestamp >= ago(1h)
| order by timestamp desc
```

**Expected**: Entry around 02:00, 14:00, or 20:00 UTC

---

## Phase 4: Health Dashboard Setup

### Step 1: Create Dashboard in Azure Portal
1. Go to Azure Portal
2. Create new Dashboard
3. Add tiles:
   - Metric chart (Batch Creation Frequency)
   - Status badge (from health endpoint)
   - Error rate chart (from Application Insights)
   - Latest batch info

### Step 2: Configure Endpoint Polling
```json
{
  "endpoint": "https://terprint-menu-downloader.azurewebsites.net/api/health/batches",
  "poll_interval_minutes": 15,
  "dashboard_refresh_interval_seconds": 60
}
```

### Step 3: Wire Alerts to Dashboard
- CRITICAL alerts → Red indicator
- WARNING alerts → Yellow indicator
- INFO → Green indicator

---

## Phase 5: Post-Deployment Validation

### Checklist
- [ ] Azure Function v1.3.3 deployed successfully
- [ ] Manual trigger `/api/run` creates batch file
- [ ] Batch file appears in Azure Data Lake within 5 minutes
- [ ] Application Insights shows `[BATCHES]` logs with no CRITICAL errors
- [ ] Health endpoint `/api/health/batches` returns healthy status
- [ ] Timer trigger fires at scheduled times (02:00, 14:00, 20:00 UTC)
- [ ] No CRITICAL errors in first 24 hours of scheduled triggers
- [ ] Dashboard displays correct metrics and status
- [ ] Alert rules are active and tested

### Testing Alert Rules
```powershell
# Test each alert manually:

# 1. Critical Error Alert
# - Simulate error by stopping Azure auth
# - Expect CRITICAL alert within 15 min

# 2. No Batch Alert
# - Monitor for 24h+ without batch
# - Expect CRITICAL alert after 24h

# 3. Upload Failure
# - Disconnect Data Lake temporarily
# - Trigger /api/run
# - Expect CRITICAL alert within 5 min

# 4. High Error Rate
# - Introduce logging error in code
# - Deploy and run
# - Expect WARNING alert within 1h
```

---

## Phase 6: Rollback Procedure (if needed)

### If v1.3.3 causes issues:
```powershell
# Revert to v1.3.0
cd azure_function

# Update requirements.txt
sed -i 's/terprint-menu-downloader>=1.3.3/terprint-menu-downloader>=1.3.0/g' requirements.txt

# Redeploy
func azure functionapp publish terprint-menu-downloader --build remote

# Restart function app
az functionapp restart \
  --name terprint-menu-downloader \
  --resource-group rg-dev-terprint-menudownloader
```

---

## Success Criteria

**After 24 hours of deployment:**
- ✅ Minimum 3 batch files created (one per timer trigger)
- ✅ All 5 dispensaries present in batches
- ✅ 0 CRITICAL errors in logs
- ✅ Health endpoint returns "healthy" status
- ✅ Average batch processing latency < 5 minutes
- ✅ No failed uploads to Azure Data Lake

**After 7 days:**
- ✅ 21 batch files created (3 per day × 7 days)
- ✅ Consolidation success rate ≥ 99%
- ✅ Upload success rate = 100%
- ✅ No alert escalations

---

## Troubleshooting

### Batch File Not Created
1. Check `/api/run` response status
2. Review Application Insights for [BATCHES] logs
3. Verify Azure Data Lake container accessible
4. Check Managed Identity has Storage Blob Data Contributor role

### Timer Trigger Not Firing
1. Verify function app is running: `az functionapp show --name terprint-menu-downloader --query state`
2. Check Timer trigger binding in function_app.py
3. Restart function app: `az functionapp restart --name terprint-menu-downloader --resource-group rg-dev-terprint-menudownloader`
4. Monitor for next scheduled time in Application Insights

### CRITICAL Errors in Logs
1. Search Application Insights for "[BATCHES] CRITICAL"
2. Review error message details
3. Check if it's Azure auth, network, or consolidation logic
4. Refer to `DEVOPS_WORK_ITEMS.md` acceptance criteria

### Health Endpoint Returns "critical"
1. Check if last batch > 24 hours old
2. Verify all 5 dispensaries present: `batch_breakdown.trulieve`, `.muv`, `.sunburn`, `.cookies`, `.flowery`
3. If dispensary missing, check individual downloader status
4. Trigger manual run to create immediate batch

---

## Rollout Timeline

| Time | Action | Owner |
|------|--------|-------|
| T+0 | Deploy v1.3.3 to Azure Function | DevOps |
| T+5min | Verify deployment, test health endpoints | QA |
| T+30min | Manual trigger `/api/run` | Testing |
| T+35min | Validate batch file created in Data Lake | Testing |
| T+40min | Check Application Insights logs | Testing |
| T+2h | Monitor for next timer trigger (if scheduled) | Testing |
| T+24h | Verify 3 batches created, no critical errors | QA |
| T+7d | Confirm success rates and KPIs | Team Lead |

---

**Created**: January 13, 2025  
**Status**: Ready for Implementation  
**Next Steps**: Execute Phase 1 deployment
