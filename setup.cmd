@echo off
REM Runs setup.ps1 with Bypass for this process only (no global execution policy change).
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 pause
