param (
    [Parameter(Mandatory=$true)]
    [ValidateNotNullOrEmpty()]
    [string]$reportType
)
$ErrorActionPreference = "Stop"
Write-Host "`nStarting report $reportType coverage..." -ForegroundColor Cyan

$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"
$coverageFile = "__cov__\.coverage"
$covReportDir = "__cov__\$reportType"
$covReportFile = Join-Path -Path $covReportDir -ChildPath ".coverage"
$covReportPath = Join-Path -Path $covReportDir -ChildPath "index.html"
$covReportTitle = "$reportType Test Coverage Report"

# Check if .coverage file exists
Write-Host "Checking for .coverage file..." -ForegroundColor Green
if (-not (Test-Path -Path $coverageFile)) {
    Write-Host "Error: .coverage file not found. Please run tests to generate coverage data." -ForegroundColor Red
    exit 1
}

# Ensure report coverage directory exists
Write-Host ".coverage file found. Preparing to generate coverage report." -ForegroundColor Green
if (-not (Test-Path -Path $covReportDir)) {
    New-Item -ItemType Directory -Path $covReportDir | Out-Null
}
# Move .coverage file to report coverage directory
Move-Item -Path $coverageFile -Destination $covReportFile -Force

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to activate virtual environment." -ForegroundColor Red
    exit 1
}

# Report coverage
$reportResult = 0
try {
    # Display coverage summary
    Write-Host "===== COVERAGE SUMMARY =====" -ForegroundColor Yellow
    & python -m coverage report --data-file=$covReportFile
    $reportResult = $LASTEXITCODE
    if ($reportResult -ne 0) {
        throw "Failed to generate coverage summary report"
    }

    # Display detailed coverage report (including missing lines)
    Write-Host "===== DETAILED COVERAGE REPORT =====" -ForegroundColor Yellow
    & python -m coverage report -m --data-file=$covReportFile
    $reportResult = $LASTEXITCODE
    if ($reportResult -ne 0) {
        throw "Failed to generate detailed coverage report"
    }

    # Generate coverage report
    Write-Host "Generating HTML coverage report..." -ForegroundColor Yellow
    $env:NO_COLOR = "1"
    & python -m coverage html --data-file=$covReportFile -d $covReportDir --title $covReportTitle
    $reportResult = $LASTEXITCODE
    if ($reportResult -ne 0) {
        throw "Failed to generate HTML coverage report"
    }
}
catch {
    $reportResult = $LASTEXITCODE
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
}
finally {
    # Deactivate virtual environment
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }
    if ($reportResult -eq 0) {
        # Display coverage report location
        if (Test-Path -Path $covReportPath) {
            Start-Process $covReportPath
            Write-Host "Coverage report generated successfully!" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "Error: Coverage report file not found: $covReportPath" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Coverage report generation failed. Exit code: $reportResult" -ForegroundColor Red
        exit $reportResult
    }
}
