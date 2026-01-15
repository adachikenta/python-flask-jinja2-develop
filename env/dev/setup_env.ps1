$ErrorActionPreference = "Stop"
Write-Host "`nStarting setup base environment..." -ForegroundColor Cyan

$venvPath = ".\venv"
$pythonVersion = "python312"

function Install-ScoopPackage {
    param(
        [string]$PackageName,
        [string]$ExecutablePath,
        [int]$MaxRetries = 2
    )

    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        try {
            # Check if already installed and working
            if (Test-Path $ExecutablePath) {
                Write-Host "$PackageName is already installed." -ForegroundColor Green
                return $true
            }

            # Check if package exists but is broken
            $scoopList = scoop list 2>&1 | Out-String
            if ($scoopList -match $PackageName) {
                Write-Host "$PackageName is installed but not working. Reinstalling..." -ForegroundColor Yellow
                scoop uninstall $PackageName 2>&1 | Out-Null
                Start-Sleep -Seconds 2
            }

            # Install the package
            Write-Host "$PackageName is not installed. Installing $PackageName..." -ForegroundColor Yellow
            $output = scoop install $PackageName 2>&1

            # Wait for installation to complete
            Start-Sleep -Seconds 3

            # Verify installation
            if (Test-Path $ExecutablePath) {
                Write-Host "$PackageName installed successfully." -ForegroundColor Green
                return $true
            } else {
                $errorMsg = "$PackageName installation completed but executable not found at $ExecutablePath"
                if ($output) {
                    $errorMsg += "`nInstallation output: $output"
                }
                throw $errorMsg
            }
        }
        catch {
            $attempt++
            Write-Host "Attempt $attempt failed: $_" -ForegroundColor Red
            Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
            if ($attempt -lt $MaxRetries) {
                Write-Host "Retrying..." -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            } else {
                Write-Host "Failed to install $PackageName after $MaxRetries attempts." -ForegroundColor Red
                return $false
            }
        }
    }
    return $false
}

# check if scoop is installed
if (Get-Command scoop -ErrorAction SilentlyContinue) {
    Write-Host "scoop is already installed." -ForegroundColor Green
} else {
    # install scoop
    Write-Host "scoop is not installed. Installing scoop..." -ForegroundColor Yellow
    try {
        Invoke-Expression "& {$(Invoke-RestMethod get.scoop.sh)}"
        Write-Host "scoop installed successfully." -ForegroundColor Green

        # Reload environment variables to make scoop available in current session
        Write-Host "Reloading environment variables..." -ForegroundColor Yellow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        # Verify scoop is now available
        if (Get-Command scoop -ErrorAction SilentlyContinue) {
            Write-Host "scoop is now available in current session." -ForegroundColor Green
        } else {
            Write-Host "Warning: scoop installed but not found in PATH. You may need to restart the terminal." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Failed to install scoop: $_" -ForegroundColor Red
        exit 1
    }
}

# check if git of scoop is installed
$scoopgit = "$env:USERPROFILE\scoop\apps\git\current\bin\git.exe"
$gitInstalled = Install-ScoopPackage -PackageName "git" -ExecutablePath $scoopgit
if (-not $gitInstalled) {
    Write-Host "Failed to install git. Exiting..." -ForegroundColor Red
    exit 1
}

# Configure git settings
Write-Host "Configuring git settings..." -ForegroundColor Yellow
try {
    # Create .gitconfig if it doesn't exist
    $gitConfigPath = "$env:USERPROFILE\.gitconfig"
    if (-not (Test-Path $gitConfigPath)) {
        Write-Host ".gitconfig not found. Creating..." -ForegroundColor Yellow
        New-Item -Path $gitConfigPath -ItemType File -Force | Out-Null
    }

    # Set schannel for SSL backend
    & $scoopgit config --global http.sslbackend schannel 2>&1 | Out-Null
    Write-Host "git sslbackend set to schannel." -ForegroundColor Green

    # Disable SSL revocation check to avoid CRYPT_E_NO_REVOCATION_CHECK error
    & $scoopgit config --global http.schannelCheckRevoke false 2>&1 | Out-Null
    Write-Host "git SSL revocation check disabled." -ForegroundColor Green
}
catch {
    Write-Host "Warning: Could not configure git settings: $_" -ForegroundColor Yellow
    Write-Host "Attempting to continue anyway..." -ForegroundColor Yellow
}

# check versions bucket
Write-Host "Checking versions bucket..." -ForegroundColor Yellow
$buckets = scoop bucket list 2>&1 | Out-String

if ($buckets -match "versions") {
    Write-Host "versions bucket is already added." -ForegroundColor Green
} else {
    Write-Host "Adding versions bucket..." -ForegroundColor Yellow
    try {
        $addBucketOutput = scoop bucket add versions 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to add versions bucket. Exit code: $LASTEXITCODE`nOutput: $addBucketOutput"
        }

        # Verify the bucket was added
        Start-Sleep -Seconds 2
        $ErrorActionPreference = "Continue"
        $bucketsAfter = scoop bucket list 2>&1 | Out-String
        $ErrorActionPreference = "Stop"

        if ($bucketsAfter -notmatch "versions") {
            throw "versions bucket was not found after installation"
        }

        Write-Host "versions bucket added successfully." -ForegroundColor Green
    }
    catch {
        Write-Host "Error: Could not add versions bucket: $_" -ForegroundColor Red
        Write-Host "The versions bucket is required to install $pythonVersion" -ForegroundColor Red
        Write-Host "Please check your network connection and proxy settings." -ForegroundColor Yellow
        exit 1
    }
}

# check if gettext of scoop installed (basketballapp specific)
$scoopgettext = "$env:USERPROFILE\scoop\apps\gettext\current\bin\msgfmt.exe"
if (Test-Path $scoopgettext) {
    Write-Host "gettext of scoop is already installed." -ForegroundColor Green
} else {
    # install gettext
    Write-Host "gettext is not installed. Installing gettext..." -ForegroundColor Yellow
    $gettextInstalled = Install-ScoopPackage -PackageName "gettext" -ExecutablePath $scoopgettext
    if (-not $gettextInstalled) {
        Write-Host "Warning: Failed to install gettext. Translation features may not work." -ForegroundColor Yellow
    }
}

# check if python of scoop is installed
$scooppython = "$env:USERPROFILE\scoop\apps\$pythonVersion\current\python.exe"
$pythonInstalled = Install-ScoopPackage -PackageName $pythonVersion -ExecutablePath $scooppython
if (-not $pythonInstalled) {
    Write-Host "Failed to install Python. Exiting..." -ForegroundColor Red
    exit 1
}

# Verify Python is working
try {
    $pythonVersionOutput = & $scooppython --version 2>&1
    Write-Host "Python version: $pythonVersionOutput" -ForegroundColor Green
}
catch {
    Write-Host "Python executable exists but is not working properly: $_" -ForegroundColor Red
    exit 1
}

# create a Python virtual environment in the 'venv' directory
if (Test-Path -Path $venvPath) {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
} else {
    Write-Host "Creating virtual environment ..." -ForegroundColor Yellow
    try {
        & $scooppython -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "venv creation failed with exit code $LASTEXITCODE"
        }
        # Verify venv was created
        $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
        if (-not (Test-Path $activateScript)) {
            throw "Virtual environment created but activation script not found"
        }
        Write-Host "Virtual environment created successfully." -ForegroundColor Green
    }
    catch {
        Write-Host "Failed to create virtual environment: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Virtual environment is located at $venvPath" -ForegroundColor Green
Write-Host "Setup completed successfully." -ForegroundColor Green
