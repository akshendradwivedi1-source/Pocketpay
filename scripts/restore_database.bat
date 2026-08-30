@echo off
REM PocketPay Windows Database Restore Runner
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe scripts\restore_database.py %*
) else (
    python scripts\restore_database.py %*
)
