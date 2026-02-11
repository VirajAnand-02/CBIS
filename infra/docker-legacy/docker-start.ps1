# Start All Docker Services
# PowerShell script to start all CBIS microservices using docker-compose

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Starting CBIS Docker Stack (cbis-stack)" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    docker version | Out-Null
} catch {
    Write-Host "Error: Docker is not running or not installed" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

# Check if docker-compose is available
try {
    docker-compose version | Out-Null
} catch {
    Write-Host "Error: docker-compose is not installed" -ForegroundColor Red
    exit 1
}

Write-Host "Docker is running ✓" -ForegroundColor Green
Write-Host ""

# Check if images exist
Write-Host "Checking for existing images..." -ForegroundColor Yellow
$imagesExist = $true
$requiredImages = @("cbis-clip", "cbis-type-router-v2", "cbis-nima", "cbis-query-optimizer", "cbis-search-router", "cbis-face-detection")

foreach ($image in $requiredImages) {
    $result = docker images -q $image 2>$null
    if (-not $result) {
        Write-Host "  ✗ Image not found: $image" -ForegroundColor Red
        $imagesExist = $false
    } else {
        Write-Host "  ✓ Image found: $image" -ForegroundColor Green
    }
}

Write-Host ""

if (-not $imagesExist) {
    Write-Host "Some images are missing. Would you like to build them now? (y/n)" -ForegroundColor Yellow
    $build = Read-Host
    if ($build -eq "y" -or $build -eq "Y") {
        Write-Host "Building images..." -ForegroundColor Cyan
        docker-compose build
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Build failed. Exiting." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "Please build images first using: .\docker-build-all.ps1" -ForegroundColor Yellow
        exit 1
    }
}

# Start services
Write-Host "Starting services with docker-compose..." -ForegroundColor Cyan
Write-Host ""

docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "✓ Services started successfully!" -ForegroundColor Green
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
    
    # Wait a bit for services to start
    Write-Host "Waiting for services to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # Show running containers
    Write-Host "Running containers:" -ForegroundColor Cyan
    docker-compose ps
    
    Write-Host ""
    Write-Host "Service URLs:" -ForegroundColor Cyan
    Write-Host "  CLIP Service:       http://localhost:8000/docs" -ForegroundColor White
    Write-Host "  Type Router V2:     http://localhost:8001/docs" -ForegroundColor White
    Write-Host "  NIMA Service:       http://localhost:8002/docs" -ForegroundColor White
    Write-Host "  Query Optimizer:    http://localhost:8003/docs" -ForegroundColor White
    Write-Host "  Search Router:      http://localhost:8004/docs" -ForegroundColor White
    Write-Host "  Face Detection:     http://localhost:8005/docs" -ForegroundColor White
    
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs:          docker-compose logs -f" -ForegroundColor White
    Write-Host "  Stop services:      docker-compose down" -ForegroundColor White
    Write-Host "  Restart service:    docker-compose restart <service-name>" -ForegroundColor White
    Write-Host "  Check health:       docker-compose ps" -ForegroundColor White
    
} else {
    Write-Host ""
    Write-Host "✗ Failed to start services" -ForegroundColor Red
    Write-Host "Please check the logs: docker-compose logs" -ForegroundColor Yellow
}

Write-Host ""
