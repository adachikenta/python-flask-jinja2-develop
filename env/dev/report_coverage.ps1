param (
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$reportType
)
$ErrorActionPreference = "Stop"
$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"
$coverageFile = "__cov__\.coverage"
$covReportDir = "__cov__\$reportType"
$covReportFile = Join-Path -Path $covReportDir -ChildPath ".coverage"
$covReportPath = Join-Path -Path $covReportDir -ChildPath "index.html"
$covReportTitle = "$reportType Test Coverage Report"

Write-Host "Starting coverage report generation..." -ForegroundColor Cyan

# Check if .coverage file exists
Write-Host "Checking for .coverage file..." -ForegroundColor Green
if (-not (Test-Path -Path $coverageFile)) {
    Write-Host "Error: .coverage file not found. Please run tests to generate coverage data." -ForegroundColor Red
    exit 1
}

# Ensure report coverage directory exists
Write-Host "`n.coverage file found. Preparing to generate coverage report." -ForegroundColor Green
if (-not (Test-Path -Path $covReportDir)) {
    New-Item -ItemType Directory -Path $covReportDir | Out-Null
}
# Move .coverage file to report coverage directory
Move-Item -Path $coverageFile -Destination $covReportFile -Force

# Run common validation and activate venv
Write-Host "`nValidating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

try {
    # Display coverage summary
    Write-Host "`n===== COVERAGE SUMMARY =====" -ForegroundColor Cyan
    & python -m coverage report --data-file=$covReportFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate coverage summary report"
    }

    # Display detailed coverage report (including missing lines)
    Write-Host "`n===== DETAILED COVERAGE REPORT =====" -ForegroundColor Cyan
    & python -m coverage report -m --data-file=$covReportFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Detailed coverage report had issues, but continuing..." -ForegroundColor Yellow
    }

    # Generate coverage report
    Write-Host "`n===== GENERATING COVERAGE REPORT =====" -ForegroundColor Cyan
    & python -m coverage html --data-file=$covReportFile -d $covReportDir --title $covReportTitle
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate HTML coverage report"
    }

    # Display coverage report location
    if (Test-Path -Path $covReportPath) {
        Write-Host "`nCoverage report successfully generated:" -ForegroundColor Green
        Write-Host $covReportPath -ForegroundColor Yellow
        Start-Process $covReportPath
    } else {
        Write-Host "`nWarning: coverage report file not found." -ForegroundColor Yellow
        throw "Coverage report generation failed"
    }
    Write-Host "`nCoverage report generation completed." -ForegroundColor Green
}
catch {
    Write-Host "An error occurred during coverage report generation: $_" -ForegroundColor Red
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
