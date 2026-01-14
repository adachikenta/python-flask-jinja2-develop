$ErrorActionPreference = "Stop"
Write-Host "`nStarting translation file conversion..." -ForegroundColor Cyan

$translations = ".\translations"

# Check if translations directory exists
if (-not (Test-Path $translations)) {
    Write-Host "Error: translations directory not found at: $translations" -ForegroundColor Red
    exit 1
}

# Convert .po files to .mo files
$convertResult = 0
try {
    Write-Host "Processing translation files..." -ForegroundColor Yellow
    $processedCount = 0
    $skippedCount = 0

    Get-ChildItem $translations -Recurse -Filter *.po | ForEach-Object {
        $po = $_.FullName
        $mo = $po -replace '\.po$', '.mo'

        if (!(Test-Path $mo) -or ((Get-Item $po).LastWriteTime -gt (Get-Item $mo).LastWriteTime)) {
            Write-Host "Converting $po -> $mo" -ForegroundColor Yellow
            & msgfmt -o $mo $po
            $convertResult = $LASTEXITCODE
            if ($convertResult -ne 0) {
                throw "Failed to convert $po to $mo"
            }
            $processedCount++
        } else {
            Write-Host "Skipping $po (up-to-date)" -ForegroundColor Gray
            $skippedCount++
        }
    }
} catch {
    $convertResult = $LASTEXITCODE
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
} finally {
    if ($convertResult -eq 0) {
        Write-Host "Translation file conversion completed successfully!" -ForegroundColor Green
        Write-Host "Converted: $processedCount, Skipped: $skippedCount" -ForegroundColor Green
    } else {
        Write-Host "Translation file conversion failed. Exit code: $convertResult" -ForegroundColor Red
    }
}
