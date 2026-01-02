@echo off
cd /d "%~dp0"
echo Starting ANPR Entry System...
start "" "http://localhost:5000"
python main.py