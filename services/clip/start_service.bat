@echo off
echo Starting CLIP Service...
cd /d "%~dp0"
call conda activate clip-env
python -m uvicorn app:app --host 0.0.0.0 --port 8000
