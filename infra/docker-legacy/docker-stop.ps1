# Stop All Docker Services
# PowerShell script to stop all CBIS microservices

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Stopping CBIS Docker Stack (cbis-stack)" -ForegroundColor Yellow
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Ask for confirmation
Write-Host "This will stop all CBIS Docker services in the stack." -ForegroundColor Yellow
Write-Host "Do you want to continue? (y/n)" -ForegroundColor Yellow
$confirm = Read-Host

if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Operation cancelled." -ForegroundColor Gray
    exit 0
}

Write-Host ""
Write-Host "Stopping services..." -ForegroundColor Cyan

docker-compose down

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ All services stopped successfully" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  Start services again:     .\docker-start.ps1" -ForegroundColor White
    Write-Host "  Remove volumes:           docker-compose down -v" -ForegroundColor White
    Write-Host "  View stopped containers:  docker-compose ps -a" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "✗ Failed to stop services" -ForegroundColor Red
    Write-Host "Please check: docker-compose ps" -ForegroundColor Yellow
}

Write-Host ""
