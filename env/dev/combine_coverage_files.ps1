$ErrorActionPreference = "Stop"
Write-Host "`nStarting combine coverage files..." -ForegroundColor Cyan

$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"
$internalCovFile = Join-Path -Path "__cov__\internal" -ChildPath ".coverage"
$e2eCovFile = Join-Path -Path "__cov__\e2e" -ChildPath ".coverage"

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
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

# Combine .coverage files
$combineResult = 0
try {
    Write-Host "Combining coverage data..." -ForegroundColor Yellow
    & python -m coverage combine --keep --data-file=__cov__/.coverage $internalCovFile $e2eCovFile
    $combineResult = $LASTEXITCODE
    if ($combineResult -ne 0) {
        throw "Failed to combine coverage data"
    }
}
catch {
    $combineResult = $LASTEXITCODE
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
}
finally {
    # Deactivate virtual environment
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }
    if ($combineResult -eq 0) {
        Write-Host "Coverage files combined successfully!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Coverage file combination failed. Exit code: $combineResult" -ForegroundColor Red
        exit $combineResult
    }
}