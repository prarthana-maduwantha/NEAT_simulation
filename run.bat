@echo off
cd /d "%~dp0"
.\.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo Simulation exited with an error.
    pause
)

