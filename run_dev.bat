@echo off
setlocal
cd /d "%~dp0"
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
  where py >nul 2>&1 && (py -m venv venv) || (python -m venv venv)
)
if not exist "%PY%" (
  echo Could not create venv. Install Python and ensure py or python is on PATH.
  pause
  exit /b 1
)
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt

REM Optional admin bootstrap (uncomment + set values)
REM set ADMIN_EMAIL=admin@yourdomain.com
REM set ADMIN_PASSWORD=ChangeThisPassword123!
REM set ADMIN_NAME=Admin

"%PY%" bmat_run.py
endlocal
