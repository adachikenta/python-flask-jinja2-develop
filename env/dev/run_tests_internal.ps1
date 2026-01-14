# PowerShell script to run the tests

$ErrorActionPreference = "Stop"
Write-Host "`nStarting internal tests run..." -ForegroundColor Cyan

$reportPath = Join-Path -Path (Get-Location) -ChildPath "__tests__/report_internal.html"
$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Run the tests with coverage
$testResult = 0
try {
    Write-Host "Running tests with coverage..." -ForegroundColor Yellow
    pytest -v -s --html=$reportPath --cov=. --cov-config=pytest.ini --cov-report=$CoverageFormat
    $testResult = $LASTEXITCODE
} catch {
    $testResult = $LASTEXITCODE
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
} finally {
    # Additional cleanup to ensure all related processes are terminated
    try {
        Write-Host "Performing final cleanup of any remaining processes..." -ForegroundColor Yellow
        # Get all Python processes
        $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue

        foreach ($proc in $pythonProcesses) {
            try {
                # Get command line for this process using WMI
                $wmiProc = Get-WmiObject -Class Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue
                if ($wmiProc -and ($wmiProc.CommandLine -like "*app.py*" -or $wmiProc.CommandLine -like "*app.py*")) {
                    Write-Host "Final cleanup: Stopping Flask process (ID: $($proc.Id))..." -ForegroundColor Yellow
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                }
            } catch {
                Write-Host "Could not check command line for process $($proc.Id): $_" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "Error during final cleanup: $_" -ForegroundColor Yellow
    }

    # Deactivate virtual environment
    if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }

    if ($testResult -eq 0) {
        if (Test-Path -Path $reportPath) {
            Start-Process $reportPath
            Write-Host "Tests completed successfully!" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "Test report not found: $reportPath" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Tests failed or had errors. Exit code: $testResult" -ForegroundColor Red
        exit $testResult
    }
}
