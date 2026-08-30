@echo off
REM PocketPay Windows Database Backup Runner
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe scripts\backup_database.py %*
) else (
    python scripts\backup_database.py %*
)
