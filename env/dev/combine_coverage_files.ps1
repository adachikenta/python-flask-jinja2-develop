$ErrorActionPreference = "Stop"
$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"
$internalCovFile = Join-Path -Path "__cov__\internal" -ChildPath ".coverage"
$e2eCovFile = Join-Path -Path "__cov__\e2e" -ChildPath ".coverage"

Write-Host "Starting combine coverage files..." -ForegroundColor Cyan

# Check if .coverage files exist
if (-not (Test-Path -Path $internalCovFile)) {
    Write-Host "Error: not found $internalCovFile." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -Path $e2eCovFile)) {
    Write-Host "Error: not found $e2eCovFile." -ForegroundColor Red
    exit 1
}

# Run common validation and activate venv
Write-Host "`nValidating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

try {
    # Combine .coverage files
    Write-Host "`n===== COMBINING COVERAGE DATA =====" -ForegroundColor Cyan
    & python -m coverage combine --keep --data-file=__cov__/.coverage $internalCovFile $e2eCovFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to combine coverage data"
    }
}
catch {
    Write-Host "An error occurred during combining coverage files: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}
finally {
    # Deactivate virtual environment
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "`nDeactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }
}
