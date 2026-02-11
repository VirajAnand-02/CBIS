# CBIS Services Guide (No Docker)

## Structure

- `apps/next-js`: web app and APIs
- `services/clip`: CLIP embedding + caption service (port 8000)
- `services/type-router-v2`: image type classifier (port 8001)
- `services/nima`: aesthetic score service (port 8002)
- `services/search-pipeline`: query optimize + route service (port 8003)
- `services/face-detection`: face detect/recognition service (port 8005)
- `services/ocr`: OCR service (not wired into startup script yet)
- `archive/legacy`: legacy modules and old assets
- `experiments`: random scripts/media/tests
- `infra/docker-legacy`: old docker configs

## Conda Environment Mapping

- `clip-env` -> `services/clip`, `services/type-router-v2`, `services/search-pipeline`
- `nima` -> `services/nima`
- `arcface` -> `services/face-detection`
- `ocr` -> `services/ocr`

## Start Commands

### Fast way

```powershell
cd E:\programming\CBIS_Project
.\start-services.ps1
```

### Manual

```powershell
# CLIP
cd E:\programming\CBIS_Project\services\clip
conda activate clip-env
python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Type Router V2
cd E:\programming\CBIS_Project\services\type-router-v2
conda activate clip-env
python type_router_service_v2.py

# NIMA
cd E:\programming\CBIS_Project\services\nima
conda activate nima
python -m uvicorn app:app --host 0.0.0.0 --port 8002

# Search Pipeline
cd E:\programming\CBIS_Project\services\search-pipeline
conda activate clip-env
python app.py

# Face Detection
cd E:\programming\CBIS_Project\services\face-detection
conda activate arcface
python app.py

# Next.js
cd E:\programming\CBIS_Project\apps\next-js
npm run dev
```

## Notes

- Root `.env.example` still contains older variable names; update when you standardize envs.
- Docker files are intentionally moved to `infra/docker-legacy`.


