#Requires -Version 5.1
<#
.SYNOPSIS
  Creates a venv, installs dependencies, writes .env (admin + bind address), optional first start with Waitress.
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Get-RandomSecretKey {
    python -c "import secrets; print(secrets.token_hex(32))"
}

function Write-DotEnv {
    param(
        [hashtable] $Config
    )
    $tmp = [System.IO.Path]::GetTempFileName()
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($tmp, ($Config | ConvertTo-Json -Compress), $utf8NoBom)
        python (Join-Path $PSScriptRoot "setup_write_env.py") $tmp
    } finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
}

Write-Host "BMW setup (venv, pip, .env, Waitress)" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not on PATH. Install Python 3 and try again."
}

$python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $python -m venv venv
}

$activate = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
    Write-Error "venv activation script not found at $activate"
}
. $activate

Write-Host "Upgrading pip and installing requirements..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt

$existingSecret = $null
if (Test-Path ".env") {
    foreach ($line in Get-Content ".env" -Encoding UTF8) {
        if ($line -match '^\s*SECRET_KEY\s*=\s*(.+)\s*$') {
            $existingSecret = $Matches[1].Trim().Trim('"').Trim("'")
            break
        }
    }
}

$secretKey = if ($existingSecret) { $existingSecret } else { Get-RandomSecretKey }

Write-Host ""
Write-Host "Admin account (used on first database init only; existing DB keeps current password)" -ForegroundColor DarkYellow
$adminEmail = Read-Host "Admin email (e.g. admin@example.com)"
if ([string]::IsNullOrWhiteSpace($adminEmail)) {
    Write-Error "Admin email is required."
}
$adminEmail = $adminEmail.Trim().ToLowerInvariant()

$secPw = Read-Host "Admin password" -AsSecureString
if ($secPw.Length -lt 1) {
    Write-Error "Admin password is required."
}
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPw)
try {
    $adminPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
} finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
}
if ($adminPassword.Length -lt 10) {
    Write-Error "Admin password must be at least 10 characters (same as signup rules)."
}

$adminName = Read-Host "Admin display name [Admin]"
if ([string]::IsNullOrWhiteSpace($adminName)) { $adminName = "Admin" }

Write-Host ""
Write-Host "Server bind (Waitress)" -ForegroundColor Cyan
Write-Host "  Use 0.0.0.0 to listen on all interfaces, or 127.0.0.1 for local only."
$bmatHost = Read-Host "Host / IP [0.0.0.0]"
if ([string]::IsNullOrWhiteSpace($bmatHost)) { $bmatHost = "0.0.0.0" }
$bmatHost = $bmatHost.Trim()

$bmatPortStr = Read-Host "Port [5000]"
if ([string]::IsNullOrWhiteSpace($bmatPortStr)) { $bmatPortStr = "5000" }
if (-not ($bmatPortStr -match '^\d+$')) {
    Write-Error "Port must be a number."
}
$bmatPort = [int]$bmatPortStr
if ($bmatPort -lt 1 -or $bmatPort -gt 65535) {
    Write-Error "Port must be between 1 and 65535."
}

$bmatThreadsStr = Read-Host "BMAT_WAITRESS_THREADS [16]"
if ([string]::IsNullOrWhiteSpace($bmatThreadsStr)) { $bmatThreadsStr = "16" }
if (-not ($bmatThreadsStr -match '^\d+$')) {
    Write-Error "BMAT_WAITRESS_THREADS must be a number."
}
$bmatThreads = [int]$bmatThreadsStr
if ($bmatThreads -lt 1) {
    Write-Error "BMAT_WAITRESS_THREADS must be at least 1."
}

Write-DotEnv @{
    SECRET_KEY              = $secretKey
    ADMIN_EMAIL             = $adminEmail
    ADMIN_PASSWORD          = $adminPassword
    ADMIN_NAME              = $adminName
    BMAT_HOST               = $bmatHost
    BMAT_PORT               = "$bmatPort"
    BMAT_WAITRESS_THREADS   = "$bmatThreads"
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "  Run with Waitress:  .\venv\Scripts\Activate.ps1  then  python bmat_serve.py"
Write-Host "  Dev (SocketIO debug server):  python bmat_run.py"
Write-Host ""

$start = Read-Host "Start the Waitress server now? (y/N)"
if ($start -eq "y" -or $start -eq "Y") {
    python bmat_serve.py
}
