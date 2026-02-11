# Start Face Detection Service
# PowerShell script to start the Face Detection service

Write-Host "Starting Face Detection Service..." -ForegroundColor Green
Write-Host ""

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Navigate to FACE_DETECTION directory
Set-Location $PSScriptRoot

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found" -ForegroundColor Yellow
    Write-Host "Copying from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Please update .env file with your database credentials!" -ForegroundColor Red
    Write-Host "   Edit .env and set DATABASE_URL to your PostgreSQL connection string" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter after updating .env file to continue..."
}

# Install dependencies if needed
Write-Host "Checking dependencies..." -ForegroundColor Cyan
$requirements = @(
    "fastapi",
    "uvicorn",
    "insightface",
    "opencv-python",
    "numpy",
    "psycopg2-binary",
    "asyncpg"
)

$missing = @()
foreach ($pkg in $requirements) {
    python -c "import $($pkg.Replace('-', '_'))" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $missing += $pkg
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Installing missing dependencies: $($missing -join ', ')" -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Starting Face Detection Service on http://localhost:8005" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Features:" -ForegroundColor Cyan
Write-Host "  • Asynchronous queue-based processing" -ForegroundColor White
Write-Host "  • RetinaFace detection + ArcFace recognition" -ForegroundColor White
Write-Host "  • Automatic person matching and creation" -ForegroundColor White
Write-Host "  • Priority queue support" -ForegroundColor White
Write-Host ""
Write-Host "Endpoints:" -ForegroundColor Cyan
Write-Host "  POST /detect        - Enqueue face detection task" -ForegroundColor White
Write-Host "  GET  /health        - Service health and stats" -ForegroundColor White
Write-Host "  GET  /queue/stats   - Queue statistics" -ForegroundColor White
Write-Host "  GET  /docs          - API documentation" -ForegroundColor White
Write-Host ""

# Start the service
python app.py
