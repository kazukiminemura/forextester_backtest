@echo off
cd /d "%~dp0.."
python scripts/ytt_jev_vision_app.py --open-browser
if errorlevel 1 pause
