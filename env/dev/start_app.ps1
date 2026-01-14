param(
    [string]$PythonScript = ".\app.py"
)

$ErrorActionPreference = "Stop"

$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Display which script will be executed
if ($PythonScript -eq ".\app.py") {
    Write-Host "No Python script specified, using default: $PythonScript" -ForegroundColor Cyan
} else {
    Write-Host "Using Python script: $PythonScript" -ForegroundColor Cyan
}

# Verify the Python script exists
if (-not (Test-Path $PythonScript)) {
    Write-Host "Error: Python script not found: $PythonScript" -ForegroundColor Red
    exit 1
}

# Run the application
try {
    Write-Host "Starting Python script: $PythonScript" -ForegroundColor Green
    python $PythonScript
    $appResult = $LASTEXITCODE
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    $appResult = 1
} finally {
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }

    if ($appResult -eq 0) {
        Write-Host "Python script completed successfully!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "Python script exited with errors. Exit code: $appResult" -ForegroundColor Red
        exit $appResult
    }
}
