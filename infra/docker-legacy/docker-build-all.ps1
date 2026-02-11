# Build All Docker Images
# PowerShell script to build all CBIS microservices

Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Building CBIS Docker Stack (cbis-stack)" -ForegroundColor Green
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

Write-Host "Docker is running ✓" -ForegroundColor Green
Write-Host ""

# Function to build service
function Build-Service {
    param (
        [string]$Name,
        [string]$Path,
        [string]$Tag
    )
    
    Write-Host "Building $Name..." -ForegroundColor Yellow
    Write-Host "  Path: $Path" -ForegroundColor Gray
    Write-Host "  Tag: $Tag" -ForegroundColor Gray
    
    docker build -t $Tag $Path
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $Name built successfully" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to build $Name" -ForegroundColor Red
        return $false
    }
    Write-Host ""
    return $true
}

# Build each service
$services = @(
    @{Name="CLIP Service"; Path=".\CLIP"; Tag="cbis-clip:latest"},
    @{Name="Type Router V2"; Path=".\TYPE_ROUTER_V2"; Tag="cbis-type-router-v2:latest"},
    @{Name="NIMA Service"; Path=".\NIMA"; Tag="cbis-nima:latest"},
    @{Name="Query Optimizer"; Path=".\query_optimizer"; Tag="cbis-query-optimizer:latest"},
    @{Name="Search Router"; Path=".\search_router"; Tag="cbis-search-router:latest"},
    @{Name="Face Detection"; Path=".\FACE_DETECTION"; Tag="cbis-face-detection:latest"}
)

$totalServices = $services.Count
$successCount = 0
$failCount = 0

foreach ($service in $services) {
    $result = Build-Service -Name $service.Name -Path $service.Path -Tag $service.Tag
    if ($result) {
        $successCount++
    } else {
        $failCount++
    }
}

# Summary
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Build Summary" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Total services: $totalServices" -ForegroundColor White
Write-Host "Successful: $successCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "✓ All services built successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Start services: docker-compose up -d" -ForegroundColor White
    Write-Host "  2. Check status: docker-compose ps" -ForegroundColor White
    Write-Host "  3. View logs: docker-compose logs -f" -ForegroundColor White
} else {
    Write-Host "✗ Some services failed to build" -ForegroundColor Red
    Write-Host "Please check the error messages above" -ForegroundColor Yellow
}

Write-Host ""
