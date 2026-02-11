# Start OCR Service
Write-Host "Starting OCR Service..." -ForegroundColor Cyan
Write-Host "Service will run on http://localhost:8004" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment if exists
if (Test-Path "../cbis_venv/bin/Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & ../cbis_venv/bin/Activate.ps1
}

# Start the service
python app.py
