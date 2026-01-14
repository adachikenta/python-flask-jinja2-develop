$ErrorActionPreference = "Stop"

$translations = ".\translations"

# Check if translations directory exists
if (-not (Test-Path $translations)) {
    Write-Host "Error: translations directory not found at: $translations" -ForegroundColor Red
    exit 1
}

# Convert .po files to .mo files
try {
    Write-Host "Processing translation files..." -ForegroundColor Yellow
    $processedCount = 0
    $skippedCount = 0

    Get-ChildItem $translations -Recurse -Filter *.po | ForEach-Object {
        $po = $_.FullName
        $mo = $po -replace '\.po$', '.mo'

        if (!(Test-Path $mo) -or ((Get-Item $po).LastWriteTime -gt (Get-Item $mo).LastWriteTime)) {
            Write-Host "Converting $po -> $mo" -ForegroundColor Cyan
            & msgfmt -o $mo $po
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to convert $po to $mo"
            }
            $processedCount++
        } else {
            Write-Host "Skipping $po (up-to-date)" -ForegroundColor Gray
            $skippedCount++
        }
    }

    Write-Host "`nTranslation files processed successfully." -ForegroundColor Green
    Write-Host "Converted: $processedCount, Skipped: $skippedCount" -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Error processing translation files: $_" -ForegroundColor Red
    Write-Host "Stack trace: $($_.ScriptStackTrace)" -ForegroundColor Red
    exit 1
}
