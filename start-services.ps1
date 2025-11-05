# Start All CBIS Services
# Run this script from PowerShell to start all services in separate windows

Write-Host "🚀 Starting CBIS Services..." -ForegroundColor Green
Write-Host ""

# PREPROCESSING SERVICES
Write-Host "=== Preprocessing Services ===" -ForegroundColor Yellow
Write-Host ""

# Start CLIP Service (Port 8000) - Image & Text Encoding
Write-Host "📦 Starting CLIP Service on port 8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\clip'; conda activate clip-env; python -m uvicorn app:app --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 2

# Start Type Router Service (Port 8001)
Write-Host "🎯 Starting Type Router Service on port 8001..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\TYPE_ROUTER'; conda activate clip-env; python type_router_service.py"

Start-Sleep -Seconds 2

# Start NIMA Service (Port 8002)
Write-Host "⭐ Starting NIMA Service on port 8002..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\NIMA'; conda activate clip-env; python -m uvicorn app:app --host 0.0.0.0 --port 8002"

Start-Sleep -Seconds 2

# SEARCH PIPELINE SERVICES
Write-Host ""
Write-Host "=== Search Pipeline Services ===" -ForegroundColor Yellow
Write-Host ""

# Start Query Optimizer Service (Port 8003)
Write-Host "🔍 Starting Query Optimizer Service on port 8003..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\query_optimizer'; conda activate clip-env; python app.py"

Start-Sleep -Seconds 2

# Start Search Router Service (Port 8004)
Write-Host "🧭 Starting Search Router Service on port 8004..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\search_router'; conda activate clip-env; python app.py"

Start-Sleep -Seconds 2

# WEB APPLICATION
Write-Host ""
Write-Host "=== Web Application ===" -ForegroundColor Yellow
Write-Host ""

# Start Next.js Application (Port 3000)
Write-Host "🌐 Starting Next.js Application on port 3000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\next-js'; npm run dev"

Write-Host ""
Write-Host "✅ All services started!" -ForegroundColor Green
Write-Host ""
Write-Host "Preprocessing Services:" -ForegroundColor Yellow
Write-Host "  - CLIP Service:          http://localhost:8000  (Image & Text Encoding)" -ForegroundColor White
Write-Host "  - Type Router:           http://localhost:8001  (Image Classification)" -ForegroundColor White
Write-Host "  - NIMA Service:          http://localhost:8002  (Aesthetic Scoring)" -ForegroundColor White
Write-Host ""
Write-Host "Search Pipeline Services:" -ForegroundColor Yellow
Write-Host "  - Query Optimizer:       http://localhost:8003  (Query Processing)" -ForegroundColor White
Write-Host "  - Search Router:         http://localhost:8004  (Search Strategy)" -ForegroundColor White
Write-Host ""
Write-Host "Web Application:" -ForegroundColor Yellow
Write-Host "  - Next.js App:           http://localhost:3000  (Main Interface)" -ForegroundColor White
Write-Host ""
Write-Host "💡 Press Ctrl+C in each window to stop the services" -ForegroundColor Gray
Write-Host "📖 See SEARCH_PIPELINE.md for search documentation" -ForegroundColor Gray
Write-Host ""
