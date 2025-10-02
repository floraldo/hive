@echo off
REM Quick Golden Rules validation for developers (Windows)
REM Run this before committing to check architectural compliance
REM
REM Usage:
REM   scripts\check-golden-rules.bat                 Full validation
REM   scripts\check-golden-rules.bat --incremental   Changed files only
REM   scripts\check-golden-rules.bat --quick         Quick mode
REM   scripts\check-golden-rules.bat -i -q           Incremental + quick

echo 🔍 Validating Golden Rules compliance...
echo.

REM Default to incremental mode if no args provided
if "%~1"=="" (
    echo 💡 Running incremental validation ^(changed files only^)
    echo    Use --help to see all options
    echo.
    python scripts\validate_golden_rules.py --incremental
) else (
    python scripts\validate_golden_rules.py %*
)

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ All Golden Rules passed!
) else (
    echo.
    echo ❌ Golden Rules violations detected
    echo Run 'python scripts\validate_golden_rules.py --help' for options
)

exit /b %ERRORLEVEL%