# Copy copilot-instructions.md to all Terprint repositories
# Run from terprint-config repo root
# Note: Output file is copilot-instructions.md for GitHub Copilot auto-discovery

$sourceFile = Join-Path $PSScriptRoot ".github\copilot-instructions.md"
$baseDir = "c:\Users\JamiesonGill\Documents\GitHub\Acidni-LLC"

# List of all Terprint repositories (simple repos with .github at root)
$repos = @(
    "terprint-ai-chat",
    "terprint-ai-recommender",
    "terprint-ai-deals",
    "terprint-coa-extractor",
    "terprint-batch-processor",
    "terprint-powerbi-visuals",
    "Terprint.Web",
    "Terprint.Tests",
    "func-terprint-communications",
    "azure-storage",
    "azure-keyvault",
    "terprint-ai-health",
    "terprint-tests",
    "terprint-menudownloader"
)

# Special repos with nested project folders (terprint-python monorepo)
$nestedRepos = @(
    @{ Path = "terprint-python\Terprint.Python.MenuDownloader"; File = "copilot-instructions.md" },
    @{ Path = "terprint-python\Terpint.Python.MenuExplorer"; File = "copilot-instructions.md" },
    @{ Path = "terprint-python\Terprint.Python.COADataExtractor"; File = "copilot-instructions.md" }
)

Write-Host "Source: $sourceFile" -ForegroundColor Cyan
Write-Host "Copying copilot-instructions.md to $($repos.Count) repositories..." -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($repo in $repos) {
    $destDir = Join-Path $baseDir "$repo\.github"
    $destFile = Join-Path $destDir "copilot-instructions.md"
    
    try {
        # Create .github directory if it doesn't exist
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            Write-Host "  Created: $destDir" -ForegroundColor DarkGray
        }
        
        # Copy the file
        Copy-Item $sourceFile $destFile -Force
        Write-Host "[OK] $repo" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host "[FAIL] $repo - $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
}

# Handle nested repos (terprint-python monorepo projects)
foreach ($nested in $nestedRepos) {
    $destDir = Join-Path $baseDir "$($nested.Path)\.github"
    $destFile = Join-Path $destDir $nested.File
    
    try {
        # Create .github directory if it doesn't exist
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
            Write-Host "  Created: $destDir" -ForegroundColor DarkGray
        }
        
        # Copy the file
        Copy-Item $sourceFile $destFile -Force
        Write-Host "[OK] $($nested.Path) -> $($nested.File)" -ForegroundColor Green
        $successCount++
    }
    catch {
        Write-Host "[FAIL] $($nested.Path) - $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
}

Write-Host ""
Write-Host "----------------------------" -ForegroundColor Cyan
Write-Host "Success: $successCount" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "Failed:  $failCount" -ForegroundColor Red
}
Write-Host "----------------------------" -ForegroundColor Cyan
Write-Host ""

Write-Host "Done! Run with -Commit to also commit and push changes." -ForegroundColor Yellow
