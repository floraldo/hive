@echo off
REM Quick launcher for QA Agent with Live Dashboard
REM Double-click this file to start the QA Agent

echo Starting QA Agent with Live Dashboard...
echo.

cd /d %~dp0
python start_with_dashboard.py

pause
