$ErrorActionPreference = "Stop"
$reportPath = Join-Path -Path (Get-Location) -ChildPath "__tests__/report_internal.html"
$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Run the tests with coverage
try {
    Write-Host "Running tests with coverage..." -ForegroundColor Yellow
    pytest -v -s --html=$reportPath --cov=. --cov-config=pytest.ini --cov-report=$CoverageFormat
    $testResult = $LASTEXITCODE
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    $testResult = 1
} finally {
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }

    if ($testResult -eq 0) {
        Write-Host "Tests completed successfully!" -ForegroundColor Green

        Write-Host "Done!" -ForegroundColor Green
        if (Test-Path -Path $reportPath) {
            Start-Process $reportPath
        }

        # Generate coverage report
        $reportCoverageScript = Join-Path $PSScriptRoot "report_coverage_internal.ps1"
        if (Test-Path -Path $reportCoverageScript) {
            Write-Host "`nGenerating coverage report..." -ForegroundColor Cyan
            & $reportCoverageScript
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Coverage report generation failed with exit code: $LASTEXITCODE" -ForegroundColor Red
                exit $LASTEXITCODE
            }
        }

        # Cleanup any remaining Python processes
        $pythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like '*app.py*' }
        if ($pythonProcesses) {
            $pythonProcesses | Stop-Process -Force
            Write-Host "Cleaned up Python processes." -ForegroundColor Yellow
        }
        exit 0
    } else {
        Write-Host "Tests failed or had errors. Exit code: $testResult" -ForegroundColor Red
        exit $testResult
    }
}
