@echo off
REM Setup script for Hive platform conda environment
REM Creates Python 3.11 environment with all necessary dependencies

echo ============================================================
echo Hive Platform Environment Setup
echo ============================================================
echo.

REM Check if conda is available
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Conda not found in PATH
    echo Please ensure Anaconda/Miniconda is installed and in PATH
    exit /b 1
)

echo [1/5] Creating 'hive' conda environment with Python 3.11...
call conda create -n hive python=3.11 -y
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create conda environment
    exit /b 1
)

echo.
echo [2/5] Activating 'hive' environment...
call conda activate hive
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate environment
    exit /b 1
)

echo.
echo [3/5] Installing Poetry...
pip install poetry
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Poetry
    exit /b 1
)

echo.
echo [4/5] Configuring Poetry to use conda environment...
poetry config virtualenvs.create false

echo.
echo [5/5] Installing project dependencies...
cd /d C:\git\hive\apps\ecosystemiser
poetry install
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Poetry install encountered issues - this may be expected
    echo You can retry with: conda activate hive ^&^& cd C:\git\hive\apps\ecosystemiser ^&^& poetry install
)

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Activate environment: conda activate hive
echo   2. Verify Python: python --version  (should be 3.11.x)
echo   3. Test imports: python -c "from hive_db import get_sqlite_connection; print('SUCCESS')"
echo   4. Run validation: cd C:\git\hive\apps\ecosystemiser ^&^& python scripts\validate_database_logging.py
echo.
echo To use this environment in VSCode/IDEs:
echo   - Select Python interpreter: C:\Users\flori\Anaconda\envs\hive\python.exe
echo   - Or let IDE auto-detect the 'hive' conda environment
echo.
