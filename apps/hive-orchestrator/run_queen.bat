@echo off
REM Run the Queen orchestrator on Windows
REM This script ensures proper module loading and Python paths

echo ========================================
echo Starting Hive Queen Orchestrator
echo ========================================

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0

REM Run the Python script with all arguments passed through
python "%SCRIPT_DIR%run_queen.py" %*

REM Check if it failed
if %ERRORLEVEL% neq 0 (
    echo.
    echo ERROR: Queen failed with exit code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)