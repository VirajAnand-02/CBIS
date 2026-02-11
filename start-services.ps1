# Start All CBIS Services (no Docker)
# Run from: E:\programming\CBIS_Project

Write-Host "Starting CBIS services..." -ForegroundColor Green
Write-Host ""

# CLIP (clip-env)
Write-Host "Starting CLIP on :8000 (env: clip-env)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\services\clip'; conda activate clip-env; python -m uvicorn app:app --host 0.0.0.0 --port 8000"
Start-Sleep -Seconds 2

# Type Router V2 (clip-env)
Write-Host "Starting Type Router V2 on :8001 (env: clip-env)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\services\type-router-v2'; conda activate clip-env; python type_router_service_v2.py"
Start-Sleep -Seconds 2

# NIMA (nima)
Write-Host "Starting NIMA on :8002 (env: nima)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\services\nima'; conda activate nima; python -m uvicorn app:app --host 0.0.0.0 --port 8002"
Start-Sleep -Seconds 2

# Search Pipeline (clip-env)
Write-Host "Starting Search Pipeline on :8003 (env: clip-env)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\services\search-pipeline'; conda activate clip-env; python app.py"
Start-Sleep -Seconds 2

# Face Detection (arcface)
Write-Host "Starting Face Detection on :8005 (env: arcface)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\services\face-detection'; conda activate arcface; python app.py"
Start-Sleep -Seconds 2

# Next.js
Write-Host "Starting Next.js on :3000" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd 'E:\programming\CBIS_Project\apps\next-js'; npm run dev"

Write-Host ""
Write-Host "All services started." -ForegroundColor Green
Write-Host "CLIP            http://localhost:8000" -ForegroundColor White
Write-Host "Type Router V2  http://localhost:8001" -ForegroundColor White
Write-Host "NIMA            http://localhost:8002" -ForegroundColor White
Write-Host "Search Pipeline http://localhost:8003" -ForegroundColor White
Write-Host "Face Detection  http://localhost:8005" -ForegroundColor White
Write-Host "Next.js         http://localhost:3000" -ForegroundColor White
