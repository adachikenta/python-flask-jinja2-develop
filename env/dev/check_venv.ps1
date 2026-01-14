param(
    [switch]$ActivateVenv = $false
)

$ErrorActionPreference = "Stop"

$venvPath = ".\venv"
$pythonVersion = "python312"
$pythonVersionNumber = "3.12"
$pythonPath = "$env:USERPROFILE\scoop\apps\$pythonVersion\current\python.exe"

# Check Python installed versions
function Test-PythonInstalled {
    if (-not (Test-Path $pythonPath)) {
        Write-Host "Python $pythonVersion is not installed at: $pythonPath" -ForegroundColor Red
        Write-Host "Please run the following commands to set up the environment:" -ForegroundColor Yellow
        Write-Host "  1. _clean.bat" -ForegroundColor Magenta
        Write-Host "  2. _setup.bat" -ForegroundColor Magenta
        return $false
    }
    Write-Host "Python $pythonVersion is installed at: $pythonPath" -ForegroundColor Green
    return $true
}

# Check if virtual environment exists
function Test-VenvExists {
    if (-not (Test-Path $venvPath)) {
        Write-Host "Virtual environment does not exist at: $venvPath" -ForegroundColor Red
        Write-Host "Please run the following commands to set up the environment:" -ForegroundColor Yellow
        Write-Host "  1. _clean.bat" -ForegroundColor Magenta
        Write-Host "  2. _setup.bat" -ForegroundColor Magenta
        return $false
    }

    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        Write-Host "Virtual environment activation script not found. Venv may be corrupted." -ForegroundColor Red
        Write-Host "Please run the following commands to set up the environment:" -ForegroundColor Yellow
        Write-Host "  1. _clean.bat" -ForegroundColor Magenta
        Write-Host "  2. _setup.bat" -ForegroundColor Magenta
        return $false
    }

    Write-Host "Virtual environment exists at: $venvPath" -ForegroundColor Green
    return $true
}

# Verify Python version in activated venv
function Test-VenvPythonVersion {
    try {
        $venvPythonVersion = python --version 2>&1
        Write-Host "Using Python: $venvPythonVersion" -ForegroundColor Green

        if ($venvPythonVersion -notmatch "Python $pythonVersionNumber") {
            Write-Host "Warning: Expected Python $pythonVersionNumber but found: $venvPythonVersion" -ForegroundColor Yellow
            Write-Host "Virtual environment may have been created with a different Python version." -ForegroundColor Yellow
            return $false
        }
        return $true
    }
    catch {
        Write-Host "Failed to check Python version in venv: $_" -ForegroundColor Red
        return $false
    }
}

# Main validation logic
$pythonInstalled = Test-PythonInstalled
if (-not $pythonInstalled) {
    exit 1
}

$venvExists = Test-VenvExists
if (-not $venvExists) {
    exit 1
}

# Only proceed to activation if we reach here (venv exists)
# If ActivateVenv flag is set, activate and verify version
if ($ActivateVenv) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    try {
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        . $activateScript
        Write-Host "Virtual environment activated." -ForegroundColor Green

        $versionOk = Test-VenvPythonVersion
        if (-not $versionOk) {
            # Warning only, don't exit
            Write-Host "Continuing with current Python version..." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Failed to activate virtual environment: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "All checks passed successfully." -ForegroundColor Green
exit 0
