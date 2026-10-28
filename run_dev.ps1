#Requires -Version 5.1
# Dev server. If execution policy blocks this file, use run_dev.bat or run_dev.cmd instead.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (!(Test-Path $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -m venv venv
    } else {
        python -m venv venv
    }
    $venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

# Optional admin bootstrap
# $env:ADMIN_EMAIL="admin@yourdomain.com"
# $env:ADMIN_PASSWORD="ChangeThisPassword123!"
# $env:ADMIN_NAME="Admin"

& $venvPython bmat_run.py
