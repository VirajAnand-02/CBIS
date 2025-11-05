# Test CBIS Preprocessing Pipeline
# This script tests each service individually

Write-Host "🧪 Testing CBIS Services..." -ForegroundColor Green
Write-Host ""

# Test 1: CLIP Service
Write-Host "1️⃣  Testing CLIP Service (http://localhost:8000)..." -ForegroundColor Cyan
try {
    $clipHealth = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
    Write-Host "   ✅ CLIP Service is running on $($clipHealth.device)" -ForegroundColor Green
} catch {
    Write-Host "   ❌ CLIP Service is not responding" -ForegroundColor Red
    Write-Host "   Run: cd clip; python -m uvicorn app:app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
}
Write-Host ""

# Test 2: Type Router Service
Write-Host "2️⃣  Testing Type Router Service (http://localhost:8001)..." -ForegroundColor Cyan
try {
    $routerHealth = Invoke-RestMethod -Uri "http://localhost:8001/health" -Method GET
    Write-Host "   ✅ Type Router is running" -ForegroundColor Green
    Write-Host "   Attributes: $($routerHealth.attributes -join ', ')" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Type Router is not responding" -ForegroundColor Red
    Write-Host "   Run: cd TYPE_ROUTER; python type_router_service.py" -ForegroundColor Yellow
}
Write-Host ""

# Test 3: Next.js Application
Write-Host "3️⃣  Testing Next.js Application (http://localhost:3000)..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3000" -Method GET -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Next.js Application is running" -ForegroundColor Green
    }
} catch {
    Write-Host "   ❌ Next.js Application is not responding" -ForegroundColor Red
    Write-Host "   Run: cd next-js; npm run dev" -ForegroundColor Yellow
}
Write-Host ""

# Test 4: Preprocessing API
Write-Host "4️⃣  Testing Preprocessing API..." -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod -Uri "http://localhost:3000/api/preprocessing" -Method GET
    Write-Host "   ✅ Preprocessing API is available" -ForegroundColor Green
    Write-Host "   Current queue: $($status.count) jobs" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Preprocessing API is not responding" -ForegroundColor Red
}
Write-Host ""

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""
Write-Host "📝 To test the full pipeline:" -ForegroundColor Yellow
Write-Host "   1. Upload an image at http://localhost:3000" -ForegroundColor White
Write-Host "   2. Watch the 'Processing - X' counter in the sidebar" -ForegroundColor White
Write-Host "   3. Check the logs in each service terminal" -ForegroundColor White
Write-Host "   4. Find results in: next-js/storage/blobs/{blobId}.processing.json" -ForegroundColor White
Write-Host ""
