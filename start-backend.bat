@echo off
cd /d "D:\claude软件\金价监测\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
pause
