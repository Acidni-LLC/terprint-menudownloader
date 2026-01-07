# Terprint Menu Downloader - Container App Deployment Script
# This script builds and deploys the container app to Azure

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "rg-dev-terprint-menudownloader",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "eastus2",
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerAppName = "ca-terprint-menudownloader",
    
    [Parameter(Mandatory=$false)]
    [string]$ContainerRegistryName = "acrterprint",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageName = "terprint-menu-downloader",
    
    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Terprint Menu Downloader - Container App Deployment" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Get the script directory (container_app folder)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "`nWorking directory: $ScriptDir"

# Step 1: Check if ACR exists, if not create it
Write-Host "`n[1/6] Checking Azure Container Registry..." -ForegroundColor Yellow
$acrExists = az acr show --name $ContainerRegistryName --resource-group $ResourceGroup --query "name" -o tsv 2>$null
if (-not $acrExists) {
    Write-Host "Creating Azure Container Registry: $ContainerRegistryName" -ForegroundColor Green
    az acr create `
        --name $ContainerRegistryName `
        --resource-group $ResourceGroup `
        --sku Basic `
        --admin-enabled true `
        --location $Location
} else {
    Write-Host "ACR already exists: $ContainerRegistryName" -ForegroundColor Green
}

# Step 2: Build and push the Docker image
Write-Host "`n[2/6] Building and pushing Docker image..." -ForegroundColor Yellow
$FullImageName = "$ContainerRegistryName.azurecr.io/$ImageName`:$ImageTag"
Write-Host "Image: $FullImageName"

# Build using ACR Tasks (no local Docker needed)
Push-Location $ScriptDir
try {
    az acr build `
        --registry $ContainerRegistryName `
        --image "$ImageName`:$ImageTag" `
        --file Dockerfile `
        .
} finally {
    Pop-Location
}

# Step 3: Check/Create Container Apps Environment
Write-Host "`n[3/6] Checking Container Apps Environment..." -ForegroundColor Yellow
$EnvName = "cae-terprint"
$envExists = az containerapp env show --name $EnvName --resource-group $ResourceGroup --query "name" -o tsv 2>$null
if (-not $envExists) {
    Write-Host "Creating Container Apps Environment: $EnvName" -ForegroundColor Green
    az containerapp env create `
        --name $EnvName `
        --resource-group $ResourceGroup `
        --location $Location
} else {
    Write-Host "Environment already exists: $EnvName" -ForegroundColor Green
}

# Step 4: Get ACR credentials
Write-Host "`n[4/6] Getting ACR credentials..." -ForegroundColor Yellow
$acrPassword = az acr credential show --name $ContainerRegistryName --query "passwords[0].value" -o tsv

# Step 5: Create/Update Container App
Write-Host "`n[5/6] Deploying Container App..." -ForegroundColor Yellow

# Get environment variables from existing function app (if any)
$existingSettings = az functionapp config appsettings list `
    --name "terprint-menu-downloader" `
    --resource-group $ResourceGroup `
    -o json 2>$null | ConvertFrom-Json

# Build environment variable string
$envVars = @(
    "AZURE_STORAGE_ACCOUNT=storageacidnidatamover",
    "AZURE_STORAGE_CONTAINER=jsonfiles"
)

foreach ($setting in $existingSettings) {
    if ($setting.name -match "^(AZURE_|BATCH_PROCESSOR|APPLICATIONINSIGHTS)") {
        $envVars += "$($setting.name)=$($setting.value)"
    }
}

$envVarString = $envVars -join " "

$appExists = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query "name" -o tsv 2>$null
if (-not $appExists) {
    Write-Host "Creating Container App: $ContainerAppName" -ForegroundColor Green
    
    az containerapp create `
        --name $ContainerAppName `
        --resource-group $ResourceGroup `
        --environment $EnvName `
        --image $FullImageName `
        --registry-server "$ContainerRegistryName.azurecr.io" `
        --registry-username $ContainerRegistryName `
        --registry-password $acrPassword `
        --target-port 8000 `
        --ingress external `
        --cpu 1 `
        --memory 2Gi `
        --min-replicas 1 `
        --max-replicas 1 `
        --env-vars $envVars `
        --system-assigned
} else {
    Write-Host "Updating Container App: $ContainerAppName" -ForegroundColor Green
    
    az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroup `
        --image $FullImageName
}

# Step 6: Get the container app URL
Write-Host "`n[6/6] Getting Container App URL..." -ForegroundColor Yellow
$fqdn = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Write-Host "`n======================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host "`nContainer App URL: https://$fqdn" -ForegroundColor Cyan
Write-Host "`nEndpoints:"
Write-Host "  - Health: https://$fqdn/health"
Write-Host "  - Status: https://$fqdn/status"
Write-Host "  - Run:    https://$fqdn/run (POST)"
Write-Host "  - Config: https://$fqdn/config"

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Grant the Container App's managed identity access to Azure Storage"
Write-Host "2. Test the health endpoint: Invoke-RestMethod https://$fqdn/health"
Write-Host "3. Check status: Invoke-RestMethod https://$fqdn/status"
