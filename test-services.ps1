# Test CBIS Services

Write-Host "Testing CBIS services..." -ForegroundColor Green
Write-Host ""

# CLIP
Write-Host "1. CLIP (:8000)" -ForegroundColor Cyan
try {
    $clipHealth = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
    Write-Host "   OK: CLIP running ($($clipHealth.device))" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: CLIP not responding" -ForegroundColor Red
    Write-Host "   Run: cd services\\clip; conda activate clip-env; python -m uvicorn app:app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
}
Write-Host ""

# Type Router V2
Write-Host "2. Type Router V2 (:8001)" -ForegroundColor Cyan
try {
    $routerHealth = Invoke-RestMethod -Uri "http://localhost:8001/health" -Method GET
    Write-Host "   OK: Type Router V2 running" -ForegroundColor Green
    Write-Host "   Labels: $($routerHealth.labels -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "   FAIL: Type Router V2 not responding" -ForegroundColor Red
    Write-Host "   Run: cd services\\type-router-v2; conda activate clip-env; python type_router_service_v2.py" -ForegroundColor Yellow
}
Write-Host ""

# NIMA
Write-Host "3. NIMA (:8002)" -ForegroundColor Cyan
try {
    $nimaHealth = Invoke-RestMethod -Uri "http://localhost:8002/health" -Method GET
    Write-Host "   OK: NIMA running" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: NIMA not responding" -ForegroundColor Red
    Write-Host "   Run: cd services\\nima; conda activate nima; python -m uvicorn app:app --host 0.0.0.0 --port 8002" -ForegroundColor Yellow
}
Write-Host ""

# Search Pipeline
Write-Host "4. Search Pipeline (:8003)" -ForegroundColor Cyan
try {
    $spHealth = Invoke-RestMethod -Uri "http://localhost:8003/health" -Method GET
    Write-Host "   OK: Search Pipeline running" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: Search Pipeline not responding" -ForegroundColor Red
    Write-Host "   Run: cd services\\search-pipeline; conda activate clip-env; python app.py" -ForegroundColor Yellow
}
Write-Host ""

# Face Detection
Write-Host "5. Face Detection (:8005)" -ForegroundColor Cyan
try {
    $fdHealth = Invoke-RestMethod -Uri "http://localhost:8005/health" -Method GET
    Write-Host "   OK: Face Detection running" -ForegroundColor Green
} catch {
    Write-Host "   FAIL: Face Detection not responding" -ForegroundColor Red
    Write-Host "   Run: cd services\\face-detection; conda activate arcface; python app.py" -ForegroundColor Yellow
}
Write-Host ""

# Next.js
Write-Host "6. Next.js (:3000)" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   OK: Next.js running" -ForegroundColor Green
    }
} catch {
    Write-Host "   FAIL: Next.js not responding" -ForegroundColor Red
    Write-Host "   Run: cd apps\\next-js; npm run dev" -ForegroundColor Yellow
}
