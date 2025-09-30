@echo off
REM Quick Golden Rules validation for developers (Windows)
REM Run this before committing to check architectural compliance

echo 🔍 Validating Golden Rules compliance...
echo.

python scripts\validate_golden_rules.py %*

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ All Golden Rules passed!
) else (
    echo.
    echo ❌ Golden Rules violations detected
    echo Run 'python scripts\validate_golden_rules.py --help' for options
)

exit /b %ERRORLEVEL%