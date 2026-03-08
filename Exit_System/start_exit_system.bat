@echo off
cd /d "%~dp0"
echo Starting ANPR Exit System...
start /b python main.py
timeout /t 3 /nobreak > nul
start "" "http://localhost:5001"