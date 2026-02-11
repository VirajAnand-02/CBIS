@echo off
echo Starting Type Router Service (Dummy Mode)...
cd /d "%~dp0"
call conda activate clip-env
python type_router_service.py
pause
