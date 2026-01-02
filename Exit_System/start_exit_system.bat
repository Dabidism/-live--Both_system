@echo off
cd /d "%~dp0"
echo Starting ANPR Exit System...
start "" "http://localhost:5001"
python main.py