@echo off
REM Runs run_dev.ps1 without changing machine-wide execution policy (Bypass applies only to this process).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_dev.ps1"
if errorlevel 1 pause
