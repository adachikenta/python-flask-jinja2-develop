# PowerShell script to run the tests with the Flask app running in the background

$ErrorActionPreference = "Stop"
Write-Host "`nStarting end-to-end tests run..." -ForegroundColor Cyan

$reportPath = Join-Path -Path (Get-Location) -ChildPath "__tests__/report_e2e.html"
$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

$flaskAppProcess = $null
function Start-FlaskApp {
    Write-Host "Starting Flask application in the background..." -ForegroundColor Green

    $env:FLASK_ENV = "testing"
    $env:FLASK_APP = "app.py"
    $port = 5000

    # Check if port is already in use
    try {
        $portInUse = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($portInUse) {
            Write-Host "Port $port is already in use. Trying to stop the existing process..." -ForegroundColor Yellow
            foreach ($process in $portInUse) {
                $ownerProcess = Get-Process -Id $process.OwningProcess -ErrorAction SilentlyContinue
                if ($ownerProcess) {
                    Write-Host "Stopping process: $($ownerProcess.ProcessName) (ID: $($ownerProcess.Id))" -ForegroundColor Yellow
                    Stop-Process -Id $ownerProcess.Id -Force
                    Start-Sleep -Seconds 2
                }
            }
        }
    } catch {
        Write-Host "Could not check for port conflicts: $_" -ForegroundColor Yellow
    }

    # Start Flask app using python command (venv is already activated)
    $flaskAppProcess = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru

    # Wait for app to initialize (checking if the server is up)
    Write-Host "Waiting for Flask app to initialize..." -ForegroundColor Yellow
    $startTime = Get-Date
    $timeout = New-TimeSpan -Seconds 20
    $serverUp = $false

    while (-not $serverUp -and ((Get-Date) - $startTime) -lt $timeout) {
        try {
            $connection = New-Object System.Net.Sockets.TcpClient("localhost", $port)
            if ($connection.Connected) {
                $serverUp = $true
                $connection.Close()
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if ($serverUp) {
        Write-Host "Flask application is now running on port $port" -ForegroundColor Green
    } else {
        Write-Host "Warning: Could not confirm Flask app is running. Proceeding anyway..." -ForegroundColor Yellow
    }

    # Give a bit more time for app to fully initialize
    Start-Sleep -Seconds 2

    return $flaskAppProcess
}

function Stop-FlaskApp {
    param (
        [Parameter(Mandatory=$true)]
        [System.Diagnostics.Process]$Process
    )

    Write-Host "Stopping Flask application..." -ForegroundColor Yellow

    if (-not $Process.HasExited) {
        try {
            # Try graceful termination first
            $Process.CloseMainWindow() | Out-Null
            # check .coverage file created by coverage
            if (!$Process.WaitForExit(5000)) {
                # Force kill if it doesn't respond
                $Process.Kill()
            }
            Write-Host "Flask application stopped." -ForegroundColor Green
        } catch {
            Write-Host "Error stopping Flask application: $_" -ForegroundColor Red
            try {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            } catch {
                Write-Host "Failed to force stop process: $_" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "Flask application had already stopped." -ForegroundColor Yellow
    }

    # Make sure to clean up any remaining Flask processes if needed
    try {
        # Get all Python processes
        $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue

        foreach ($proc in $pythonProcesses) {
            try {
                # Get command line for this process using WMI
                $wmiProc = Get-WmiObject -Class Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue
                if ($wmiProc -and ($wmiProc.CommandLine -like "*app.py*" -or $wmiProc.CommandLine -like "*flask*")) {
                    Write-Host "Stopping Flask process (ID: $($proc.Id))..." -ForegroundColor Yellow
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                }
            } catch {
                Write-Host "Could not check command line for process $($proc.Id): $_" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "Error during cleanup: $_" -ForegroundColor Yellow
    }
}

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Run the tests with coverage
$testResult = 0
try {
    # Start the Flask app
    $flaskAppProcess = Start-FlaskApp
    Write-Host "Running tests with coverage..." -ForegroundColor Yellow
    pytest ./tests/e2e_playwright.py -v --html=$reportPath
    $testResult = $LASTEXITCODE
} catch {
    $testResult = $LASTEXITCODE
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
} finally {
    # Stop the Flask app
    if ($flaskAppProcess -and -not $flaskAppProcess.HasExited) {
        Stop-FlaskApp -Process $flaskAppProcess
    }

    # Additional cleanup to ensure all related processes are terminated
    try {
        Write-Host "Performing final cleanup of any remaining processes..." -ForegroundColor Yellow
        # Get all Python processes
        $pythonProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue

        foreach ($proc in $pythonProcesses) {
            try {
                # Get command line for this process using WMI
                $wmiProc = Get-WmiObject -Class Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue
                if ($wmiProc -and ($wmiProc.CommandLine -like "*app.py*" -or $wmiProc.CommandLine -like "*flask*")) {
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
