# CBIS Stack Management Script
# Manage the cbis-stack Docker Compose deployment

param(
    [Parameter(Position=0)]
    [ValidateSet('up', 'down', 'restart', 'status', 'logs', 'build', 'ps', 'stats')]
    [string]$Action = 'status',
    
    [Parameter(Position=1)]
    [string]$Service = '',
    
    [switch]$Detach,
    [switch]$Build,
    [switch]$Follow,
    [switch]$Volumes,
    [switch]$Help
)

$StackName = "cbis-stack"

function Show-Help {
    Write-Host ""
    Write-Host "CBIS Stack Management" -ForegroundColor Cyan
    Write-Host "=====================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\docker-stack.ps1 [action] [service] [options]" -ForegroundColor White
    Write-Host ""
    Write-Host "Actions:" -ForegroundColor Green
    Write-Host "  up        Start the stack (default: detached)" -ForegroundColor White
    Write-Host "  down      Stop the stack" -ForegroundColor White
    Write-Host "  restart   Restart stack or specific service" -ForegroundColor White
    Write-Host "  status    Show stack status (default)" -ForegroundColor White
    Write-Host "  logs      View logs" -ForegroundColor White
    Write-Host "  build     Build images" -ForegroundColor White
    Write-Host "  ps        List containers" -ForegroundColor White
    Write-Host "  stats     Show resource usage" -ForegroundColor White
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Green
    Write-Host "  -Detach   Run in background (for 'up')" -ForegroundColor White
    Write-Host "  -Build    Rebuild images (for 'up')" -ForegroundColor White
    Write-Host "  -Follow   Follow logs (for 'logs')" -ForegroundColor White
    Write-Host "  -Volumes  Remove volumes (for 'down')" -ForegroundColor White
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Green
    Write-Host "  .\docker-stack.ps1 up" -ForegroundColor Gray
    Write-Host "  .\docker-stack.ps1 up -Build" -ForegroundColor Gray
    Write-Host "  .\docker-stack.ps1 restart face-detection" -ForegroundColor Gray
    Write-Host "  .\docker-stack.ps1 logs face-detection -Follow" -ForegroundColor Gray
    Write-Host "  .\docker-stack.ps1 down -Volumes" -ForegroundColor Gray
    Write-Host ""
}

if ($Help) {
    Show-Help
    exit 0
}

Write-Host ""
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "CBIS Stack: $StackName" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host ""

# Check Docker
try {
    docker version | Out-Null
} catch {
    Write-Host "[X] Docker is not running" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again" -ForegroundColor Yellow
    exit 1
}

switch ($Action) {
    'up' {
        Write-Host "Starting stack..." -ForegroundColor Yellow
        
        $composeArgs = @('up')
        
        if ($Detach -or !$PSBoundParameters.ContainsKey('Detach')) {
            $composeArgs += '-d'
        }
        
        if ($Build) {
            $composeArgs += '--build'
        }
        
        if ($Service) {
            $composeArgs += $Service
        }
        
        & docker-compose $composeArgs
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[OK] Stack started successfully" -ForegroundColor Green
            Write-Host ""
            Write-Host "Service URLs:" -ForegroundColor Cyan
            Write-Host "  CLIP:            http://localhost:8000/docs" -ForegroundColor White
            Write-Host "  Type Router V2:  http://localhost:8001/docs" -ForegroundColor White
            Write-Host "  NIMA:            http://localhost:8002/docs" -ForegroundColor White
            Write-Host "  Query Optimizer: http://localhost:8003/docs" -ForegroundColor White
            Write-Host "  Search Router:   http://localhost:8004/docs" -ForegroundColor White
            Write-Host "  Face Detection:  http://localhost:8005/docs" -ForegroundColor White
        }
    }
    
    'down' {
        Write-Host "Stopping stack..." -ForegroundColor Yellow
        
        $composeArgs = @('down')
        
        if ($Volumes) {
            $composeArgs += '-v'
            Write-Host "[WARN] This will remove all volumes!" -ForegroundColor Yellow
        }
        
        & docker-compose $composeArgs
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[OK] Stack stopped" -ForegroundColor Green
        }
    }
    
    'restart' {
        Write-Host "Restarting $(if ($Service) { $Service } else { 'stack' })..." -ForegroundColor Yellow
        
        if ($Service) {
            docker-compose restart $Service
        } else {
            docker-compose restart
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[OK] Restarted successfully" -ForegroundColor Green
        }
    }
    
    'status' {
        Write-Host "Stack Status:" -ForegroundColor Cyan
        Write-Host ""
        
        docker-compose ps
        
        Write-Host ""
        Write-Host "Container Health:" -ForegroundColor Cyan
        Write-Host ""
        
        $cbisContainers = docker ps --filter "name=cbis-" --format "{{.Names}}" 2>$null
        
        if ($cbisContainers) {
            foreach ($containerName in $cbisContainers) {
                $health = docker inspect --format='{{.State.Health.Status}}' $containerName 2>$null
                $status = docker inspect --format='{{.State.Status}}' $containerName 2>$null
                
                $displayName = $containerName -replace 'cbis-', ''
                
                if ($health -eq 'healthy') {
                    Write-Host "  [OK] $displayName - Healthy" -ForegroundColor Green
                } elseif ($status -eq 'running') {
                    Write-Host "  [>>] $displayName - Running" -ForegroundColor Yellow
                } else {
                    Write-Host "  [!!] $displayName - $status" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  No containers running" -ForegroundColor Yellow
        }
    }
    
    'logs' {
        if ($Service) {
            Write-Host "Logs for: $Service" -ForegroundColor Cyan
            Write-Host ""
            
            if ($Follow) {
                docker-compose logs -f $Service
            } else {
                docker-compose logs --tail=100 $Service
            }
        } else {
            Write-Host "Logs for all services:" -ForegroundColor Cyan
            Write-Host ""
            
            if ($Follow) {
                docker-compose logs -f
            } else {
                docker-compose logs --tail=50
            }
        }
    }
    
    'build' {
        if ($Service) {
            Write-Host "Building: $Service" -ForegroundColor Yellow
            docker-compose build $Service
        } else {
            Write-Host "Building all services..." -ForegroundColor Yellow
            docker-compose build
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[OK] Build completed" -ForegroundColor Green
        }
    }
    
    'ps' {
        Write-Host "Containers in stack:" -ForegroundColor Cyan
        Write-Host ""
        docker-compose ps -a
    }
    
    'stats' {
        Write-Host "Resource usage:" -ForegroundColor Cyan
        Write-Host ""
        docker stats --no-stream (docker ps --filter "name=cbis-" --format "{{.Names}}" 2>$null)
    }
}

Write-Host ""
