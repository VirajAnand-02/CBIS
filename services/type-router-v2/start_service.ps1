# Start Type Router V2 Service
# PowerShell script to start the Type Router V2 API service

Write-Host "Starting Type Router V2 Service..." -ForegroundColor Green
Write-Host ""

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Navigate to TYPE_ROUTER_V2 directory
Set-Location $PSScriptRoot

# Check if model file exists
if (-not (Test-Path "outputs/ovr_rf_clip_model.joblib")) {
    Write-Host "Warning: Model file not found at outputs/ovr_rf_clip_model.joblib" -ForegroundColor Yellow
    Write-Host "The service will run in DUMMY mode or fail if USE_DUMMY_ROUTER=false" -ForegroundColor Yellow
    Write-Host ""
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found" -ForegroundColor Yellow
    Write-Host "Creating default .env file..." -ForegroundColor Yellow
    @"
# Type Router V2 Service Configuration

# Set to true to use dummy mode (random classifications for testing)
# Set to false to use the actual trained Random Forest model
USE_DUMMY_ROUTER=true

# Model configuration (used when USE_DUMMY_ROUTER=false)
MODEL_PATH=outputs/ovr_rf_clip_model.joblib
CLIP_MODEL=openai/clip-vit-base-patch32
THRESHOLD=0.5
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "Created .env file with default settings" -ForegroundColor Green
    Write-Host ""
}

# Install dependencies if needed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
$requirements = @(
    "fastapi",
    "uvicorn",
    "pydantic",
    "python-dotenv",
    "numpy",
    "pandas",
    "joblib",
    "scikit-learn",
    "torch",
    "transformers",
    "pillow",
    "requests"
)

foreach ($pkg in $requirements) {
    python -c "import $($pkg.Replace('-', '_'))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing $pkg..." -ForegroundColor Yellow
        pip install $pkg
    }
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Starting Type Router V2 API Service on http://localhost:8001" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Start the service
python type_router_service_v2.py
