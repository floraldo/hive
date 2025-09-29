@echo off
REM Setup script for installing pre-commit hooks in the Hive platform (Windows)

echo ===================================
echo Hive Platform Pre-commit Setup
echo ===================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

REM Install pre-commit if not already installed
pre-commit --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing pre-commit...
    pip install --user pre-commit
) else (
    echo pre-commit is already installed
)

REM Install the git hooks
echo Installing pre-commit hooks...
pre-commit install

REM Run hooks on all files to verify setup
echo Running pre-commit on all files (first run may be slow)...
pre-commit run --all-files

echo.
echo Pre-commit hooks installed successfully!
echo.
echo The following checks will run automatically on git commit:
echo   - Black (code formatting)
echo   - Ruff (linting)
echo   - isort (import sorting)
echo   - MyPy (type checking)
echo   - Bandit (security scanning)
echo   - Golden Rules validation
echo   - Unicode character detection
echo   - Async function naming convention
echo.
echo To run hooks manually: pre-commit run --all-files
echo To skip hooks temporarily: git commit --no-verify
