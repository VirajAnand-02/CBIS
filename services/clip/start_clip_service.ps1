# Start CLIP Service
Write-Host "Starting CLIP Service..." -ForegroundColor Cyan

# Change to script directory
Set-Location $PSScriptRoot

# Activate conda environment and run service
& conda activate clip-env
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to activate clip-env" -ForegroundColor Red
    exit 1
}

python -m uvicorn app:app --host 0.0.0.0 --port 8000
