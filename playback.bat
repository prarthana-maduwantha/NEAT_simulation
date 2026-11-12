@echo off
cd /d "%~dp0"
echo Starting Champion Playback Simulation...
.\.venv\Scripts\python.exe playback.py
if %errorlevel% neq 0 (
    echo.
    echo Playback simulation exited with an error.
    pause
)
