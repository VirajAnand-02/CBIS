# Check Health of All Docker Services
# PowerShell script to verify all CBIS microservices are running properly

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "CBIS Stack Health Check (cbis-stack)" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Function to test service health
function Test-ServiceHealth {
    param (
        [string]$Name,
        [string]$Url,
        [int]$Port
    )
    
    Write-Host "Testing $Name..." -ForegroundColor Yellow -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host " ✓" -ForegroundColor Green
            $content = $response.Content | ConvertFrom-Json
            Write-Host "  Port: $Port" -ForegroundColor Gray
            if ($content.status) {
                Write-Host "  Status: $($content.status)" -ForegroundColor Gray
            }
            if ($content.model -or $content.model_type) {
                Write-Host "  Model: $($content.model ?? $content.model_type)" -ForegroundColor Gray
            }
            return $true
        } else {
            Write-Host " ✗ (Status: $($response.StatusCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host " ✗ (Not responding)" -ForegroundColor Red
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
        return $false
    }
}

# Check Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker version | Out-Null
    Write-Host "  ✓ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Docker is not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Check containers
Write-Host "Checking containers..." -ForegroundColor Yellow
$containers = docker-compose ps --format json 2>$null | ConvertFrom-Json

if ($containers) {
    $runningCount = 0
    foreach ($container in $containers) {
        $status = $container.State ?? $container.Status
        $name = $container.Name ?? $container.Service
        if ($status -match "running|Up") {
            Write-Host "  ✓ $name : Running" -ForegroundColor Green
            $runningCount++
        } else {
            Write-Host "  ✗ $name : $status" -ForegroundColor Red
        }
    }
    Write-Host "  Total: $runningCount running" -ForegroundColor Cyan
} else {
    Write-Host "  No containers found" -ForegroundColor Yellow
    Write-Host "  Run .\docker-start.ps1 to start services" -ForegroundColor Gray
}

Write-Host ""

# Test service endpoints
Write-Host "Testing service endpoints..." -ForegroundColor Cyan
Write-Host ""

$services = @(
    @{Name="CLIP Service"; Url="http://localhost:8000/health"; Port=8000},
    @{Name="Type Router V2"; Url="http://localhost:8001/health"; Port=8001},
    @{Name="NIMA Service"; Url="http://localhost:8002/health"; Port=8002},
    @{Name="Query Optimizer"; Url="http://localhost:8003/health"; Port=8003},
    @{Name="Search Router"; Url="http://localhost:8004/health"; Port=8004},
    @{Name="Face Detection"; Url="http://localhost:8005/health"; Port=8005}
)

$healthyCount = 0
$unhealthyCount = 0

foreach ($service in $services) {
    $result = Test-ServiceHealth -Name $service.Name -Url $service.Url -Port $service.Port
    if ($result) {
        $healthyCount++
    } else {
        $unhealthyCount++
    }
    Write-Host ""
}

# Summary
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Health Check Summary" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Total services: $($services.Count)" -ForegroundColor White
Write-Host "Healthy: $healthyCount" -ForegroundColor Green
Write-Host "Unhealthy: $unhealthyCount" -ForegroundColor $(if ($unhealthyCount -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($unhealthyCount -eq 0 -and $healthyCount -eq $services.Count) {
    Write-Host "✓ All services are healthy!" -ForegroundColor Green
} elseif ($unhealthyCount -gt 0) {
    Write-Host "⚠ Some services are unhealthy" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Cyan
    Write-Host "  1. Check logs:    docker-compose logs <service-name>" -ForegroundColor White
    Write-Host "  2. Restart:       docker-compose restart <service-name>" -ForegroundColor White
    Write-Host "  3. Rebuild:       docker-compose up -d --build <service-name>" -ForegroundColor White
} else {
    Write-Host "⚠ No services are running" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Start services with: .\docker-start.ps1" -ForegroundColor White
}

Write-Host ""

# Show API documentation URLs
if ($healthyCount -gt 0) {
    Write-Host "API Documentation:" -ForegroundColor Cyan
    foreach ($service in $services) {
        $docsUrl = $service.Url -replace "/health", "/docs"
        Write-Host "  $($service.Name): $docsUrl" -ForegroundColor White
    }
    Write-Host ""
}
