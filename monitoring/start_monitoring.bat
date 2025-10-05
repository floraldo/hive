@echo off
REM Production Monitoring Launcher
REM Starts Flask dashboard + test metrics servers

echo ============================================================
echo Hive Platform - Production Monitoring
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    exit /b 1
)

echo Starting test metrics servers on ports 8001-8003...
start "AI Apps Metrics" cmd /k "cd /d %~dp0.. && python scripts/monitoring/generate_test_metrics.py"
timeout /t 3 /nobreak >nul

echo Starting Flask dashboard on http://localhost:5000...
start "Monitoring Dashboard" cmd /k "cd /d %~dp0.. && python scripts/monitoring/simple_dashboard.py"
timeout /t 3 /nobreak >nul

echo.
echo ============================================================
echo Monitoring Stack Started
echo ============================================================
echo.
echo Flask Dashboard:    http://localhost:5000
echo AI Reviewer Metrics: http://localhost:8001/metrics
echo AI Planner Metrics:  http://localhost:8002/metrics
echo AI Deployer Metrics: http://localhost:8003/metrics
echo.
echo Press Ctrl+C in each window to stop
echo ============================================================
