$ErrorActionPreference = "Stop"

$checkVenvScript = Join-Path $PSScriptRoot "check_venv.ps1"

# Run common validation and activate venv
Write-Host "Validating Python environment..." -ForegroundColor Yellow
& $checkVenvScript -ActivateVenv
if ($LASTEXITCODE -ne 0) {
    exit 1
}

# Install required packages inside the activated venv
try {

    # Check pip in venv
    Write-Host "Checking pip in virtual environment..." -ForegroundColor Yellow

    # Get pip path and version
    $pipPath = python -c "import sys; import os; print(os.path.join(sys.prefix, 'Scripts', 'pip.exe'))" 2>&1

    if (Test-Path $pipPath) {
        Write-Host "pip is installed in venv at: $pipPath" -ForegroundColor Green

        # Get pip version
        $pipVersion = & $pipPath --version 2>&1
        Write-Host "pip version: $pipVersion" -ForegroundColor Green
    } else {
        # install pip using ensurepip
        Write-Host "pip is not found in venv. Installing pip..." -ForegroundColor Yellow
        python -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install pip"
        }

        # Verify installation
        if (Test-Path $pipPath) {
            $pipVersion = & $pipPath --version 2>&1
            Write-Host "pip installed successfully at: $pipPath" -ForegroundColor Green
            Write-Host "pip version: $pipVersion" -ForegroundColor Green
        } else {
            throw "pip installation completed but executable not found"
        }
    }

    # upgrade pip to the latest version
    Write-Host "Upgrading pip to the latest version..." -ForegroundColor Yellow
    python -m pip install --upgrade pip --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "pip upgraded successfully." -ForegroundColor Green
    } else {
        Write-Host "Warning: pip upgrade had issues but continuing..." -ForegroundColor Yellow
    }

    # install the required packages from requirements.txt
    if (Test-Path "requirements.txt") {
        Write-Host "Installing required packages for application from requirements.txt..." -ForegroundColor Yellow
        pip install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Application packages installed successfully." -ForegroundColor Green
        } else {
            throw "Failed to install packages from requirements.txt"
        }
    } else {
        Write-Host "Warning: requirements.txt not found, skipping..." -ForegroundColor Yellow
    }

    # install the required packages from ./env/dev/requirements.txt
    if (Test-Path "./env/dev/requirements.txt") {
        Write-Host "Installing required packages for tests from ./env/dev/requirements.txt..." -ForegroundColor Yellow
        pip install -r ./env/dev/requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Test packages installed successfully." -ForegroundColor Green
        } else {
            throw "Failed to install packages from ./env/dev/requirements.txt"
        }
    } else {
        Write-Host "Warning: ./env/dev/requirements.txt not found, skipping..." -ForegroundColor Yellow
    }

    # Install Playwright browsers if needed
    Write-Host "Checking for Playwright installation..." -ForegroundColor Yellow

    # Temporarily allow errors for the import check
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    $playwrightCheck = python -c "import playwright; print('installed')" 2>&1
    $playwrightInstalled = ($LASTEXITCODE -eq 0) -and ($playwrightCheck -match "installed")

    # Restore error action preference
    $ErrorActionPreference = $previousErrorAction

    if ($playwrightInstalled) {
        Write-Host "Playwright found. Installing Playwright browsers..." -ForegroundColor Yellow

        # Set environment variable to bypass SSL certificate issues in corporate environments
        $env:NODE_TLS_REJECT_UNAUTHORIZED = "0"

        try {
            # Install Playwright browsers
            python -m playwright install --with-deps 2>&1 | Out-Null

            if ($LASTEXITCODE -eq 0) {
                Write-Host "Playwright browsers installed successfully!" -ForegroundColor Green
            } else {
                Write-Host "Warning: Playwright browser installation had issues, but continuing..." -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "Warning: Could not install Playwright browsers: $_" -ForegroundColor Yellow
            Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Yellow
            Write-Host "You may need to run 'python -m playwright install' manually later." -ForegroundColor Yellow
        }
        finally {
            # Clean up environment variable
            Remove-Item env:NODE_TLS_REJECT_UNAUTHORIZED -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "Playwright not found in requirements, skipping browser installation." -ForegroundColor Gray
    }
}
catch {
    Write-Host "An error occurred during setup: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}
finally {
    # Deactivate if still active
    if (Get-Command deactivate -ErrorAction SilentlyContinue) {
        Write-Host "Deactivating virtual environment..." -ForegroundColor Yellow
        deactivate
    }
}

Write-Host "`nVirtual environment setup completed successfully!" -ForegroundColor Green
Write-Host "You can now run the application." -ForegroundColor Green
