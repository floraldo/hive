@echo off
REM Test run script for Hive MAS on Windows

echo Setting up environment...
set CLAUDE_BIN=claude
set HIVE_DISABLE_PR=1

echo Environment variables set:
echo   CLAUDE_BIN=%CLAUDE_BIN%
echo   HIVE_DISABLE_PR=%HIVE_DISABLE_PR%

echo.
echo To start the system:
echo   Terminal 1: python queen_orchestrator.py
echo   Terminal 2: python hive_status.py  
echo   Terminal 3: tail -f hive/bus/events_%date:~-4%%date:~-10,2%%date:~-7,2%.jsonl
echo.
echo To add a hint:
echo   echo Keep it minimal > hive\operator\hints\tsk_001.md
echo.
echo To interrupt:
echo   echo {"reason":"Pause for review"} > hive\operator\interrupts\tsk_001.json
echo.
echo Starting Queen orchestrator in 3 seconds...
timeout /t 3 /nobreak > nul

python queen_orchestrator.py