#requires -RunAsAdministrator
<#
.SYNOPSIS
  Builds a basic HTTP WinPE boot environment on Windows Server using:
  - IIS (web server)
  - Microsoft ADK + WinPE Add-on
  - iPXE boot script
  - WinPE files served over HTTP

.NOTES
  You still need iPXE bootloader files for clients, such as:
    - undionly.kpxe (legacy BIOS)
    - snponly.efi or ipxe.efi (UEFI)
    - wimboot
  Put those files into $WebRoot after the script finishes.

  DHCP/PXE notes:
    - Legacy BIOS boot file often: undionly.kpxe
    - UEFI x64 boot file often: snponly.efi or ipxe.efi
#>

param(
    [string]$ServerIP = "192.168.1.10",
    [string]$SiteName = "Default Web Site",
    [string]$VirtualDir = "pxe",
    [string]$WorkRoot = "C:\PXEBuild",
    [switch]$AddWin11SetupComponents
)

$ErrorActionPreference = "Stop"

# ---- Paths ----
$TempRoot      = Join-Path $WorkRoot "temp"
$DownloadRoot  = Join-Path $WorkRoot "downloads"
$AdkRoot       = "C:\Program Files (x86)\Windows Kits\10"
$WinPERoot     = Join-Path $WorkRoot "WinPE_amd64"
$WebRoot       = Join-Path $WorkRoot "web"
$MountRoot     = Join-Path $WinPERoot "mount"

# Microsoft fwlinks published on Learn for ADK 10.1.26100.2454 (Dec 2024)
$AdkSetupUrl   = "https://go.microsoft.com/fwlink/?linkid=2289980"
$WinPESetupUrl = "https://go.microsoft.com/fwlink/?linkid=2289981"

$AdkSetupExe   = Join-Path $DownloadRoot "adksetup.exe"
$WinPESetupExe = Join-Path $DownloadRoot "adkwinpesetup.exe"

function New-Folder {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Invoke-Download {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$OutFile
    )
    Write-Host "Downloading $Url -> $OutFile"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing
}

function Invoke-Exe {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string]$Arguments
    )
    Write-Host "Running: $FilePath $Arguments"
    $p = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($p.ExitCode -ne 0) {
        throw "Process failed: $FilePath exited with code $($p.ExitCode)"
    }
}

function Find-Copype {
    $candidates = @(
        (Join-Path $AdkRoot "Assessment and Deployment Kit\Deployment Tools\copype.cmd"),
        (Join-Path $AdkRoot "Assessment and Deployment Kit\Windows Preinstallation Environment\copype.cmd")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }

    $found = Get-ChildItem -Path $AdkRoot -Filter "copype.cmd" -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { return $found.FullName }

    throw "Could not find copype.cmd. ADK/WinPE install may have failed."
}

function Add-IISMimeType {
    param(
        [string]$Extension,
        [string]$MimeType
    )
    Import-Module WebAdministration

    $existing = Get-WebConfigurationProperty `
        -PSPath 'MACHINE/WEBROOT/APPHOST' `
        -Filter "system.webServer/staticContent/mimeMap[@fileExtension='$Extension']" `
        -Name "." -ErrorAction SilentlyContinue

    if (-not $existing) {
        Add-WebConfigurationProperty `
            -PSPath 'MACHINE/WEBROOT/APPHOST' `
            -Filter "system.webServer/staticContent" `
            -Name "." `
            -Value @{fileExtension=$Extension; mimeType=$MimeType} | Out-Null
    }
}

Write-Host "== Preparing folders =="
New-Folder $WorkRoot
New-Folder $TempRoot
New-Folder $DownloadRoot
New-Folder $WebRoot

Write-Host "== Installing IIS =="
Install-WindowsFeature -Name Web-Server -IncludeManagementTools | Out-Null

Write-Host "== Downloading Microsoft ADK + WinPE add-on =="
Invoke-Download -Url $AdkSetupUrl   -OutFile $AdkSetupExe
Invoke-Download -Url $WinPESetupUrl -OutFile $WinPESetupExe

Write-Host "== Installing ADK Deployment Tools =="
# Microsoft documents silent install with /quiet /installpath and /features OptionId.DeploymentTools
Invoke-Exe -FilePath $AdkSetupExe -Arguments '/quiet /norestart /ceip off /features OptionId.DeploymentTools'

Write-Host "== Installing WinPE add-on =="
# The WinPE add-on installer is installed silently here
Invoke-Exe -FilePath $WinPESetupExe -Arguments '/quiet /norestart /ceip off'

Write-Host "== Creating WinPE working files =="
$copype = Find-Copype

if (Test-Path $WinPERoot) {
    Write-Host "Existing WinPE working directory found. Reusing: $WinPERoot"
} else {
    New-Folder $WinPERoot
    cmd.exe /c "`"$copype`" amd64 `"$WinPERoot`""
    if ($LASTEXITCODE -ne 0) {
        throw "copype failed with exit code $LASTEXITCODE"
    }
}

# Optional: add Win11 setup-related optional components Microsoft mentions for launching Windows Setup from WinPE
if ($AddWin11SetupComponents) {
    Write-Host "== Adding WinPE optional components for Windows 11 setup =="
    New-Folder $MountRoot

    $WinPEOCsRoot = Join-Path $AdkRoot "Assessment and Deployment Kit\Windows Preinstallation Environment\amd64\WinPE_OCs"
    $WinPEWim     = Join-Path $WinPERoot "media\sources\boot.wim"

    if (-not (Test-Path $WinPEWim)) {
        throw "boot.wim not found at $WinPEWim"
    }

    Dism /Mount-Image /ImageFile:"$WinPEWim" /Index:1 /MountDir:"$MountRoot" | Out-Host

    $packages = @(
        "WinPE-WMI.cab",
        "WinPE-SecureStartup.cab"
    )

    foreach ($pkg in $packages) {
        $pkgPath = Join-Path $WinPEOCsRoot $pkg
        if (Test-Path $pkgPath) {
            Dism /Image:"$MountRoot" /Add-Package /PackagePath:"$pkgPath" | Out-Host
        } else {
            Write-Warning "Optional component not found: $pkgPath"
        }
    }

    Dism /Unmount-Image /MountDir:"$MountRoot" /Commit | Out-Host
}

Write-Host "== Copying WinPE web boot files =="
# Files typically needed by wimboot + iPXE
$srcBootMgr = Join-Path $WinPERoot "media\Boot\bootmgr"
$srcBCD     = Join-Path $WinPERoot "media\EFI\Microsoft\Boot\BCD"
$srcBootSdi = Join-Path $WinPERoot "media\Boot\boot.sdi"
$srcBootWim = Join-Path $WinPERoot "media\sources\boot.wim"

$dstBootDir = Join-Path $WebRoot "boot"
New-Folder $dstBootDir

foreach ($pair in @(
    @{Src=$srcBootMgr; Dst=(Join-Path $dstBootDir "bootmgr")},
    @{Src=$srcBCD;     Dst=(Join-Path $dstBootDir "BCD")},
    @{Src=$srcBootSdi; Dst=(Join-Path $dstBootDir "boot.sdi")},
    @{Src=$srcBootWim; Dst=(Join-Path $dstBootDir "boot.wim")}
)) {
    if (-not (Test-Path $pair.Src)) {
        throw "Required WinPE file not found: $($pair.Src)"
    }
    Copy-Item $pair.Src $pair.Dst -Force
}

Write-Host "== Writing iPXE menu =="
$BootIpxe = @"
#!ipxe
dhcp
set base http://$ServerIP/$VirtualDir

menu Lab PXE Boot
item --gap -- --------------------------
item winpe   Boot WinPE over HTTP
item shell   iPXE shell
choose --default winpe --timeout 5000 target && goto \${target}

:winpe
kernel \${base}/wimboot
initrd \${base}/boot/bootmgr          bootmgr
initrd \${base}/boot/BCD              BCD
initrd \${base}/boot/boot.sdi         boot.sdi
initrd \${base}/boot/boot.wim         boot.wim
boot

:shell
shell
"@

Set-Content -Path (Join-Path $WebRoot "boot.ipxe") -Value $BootIpxe -Encoding Ascii

Write-Host "== Configuring IIS =="
Import-Module WebAdministration

if (-not (Test-Path "IIS:\Sites\$SiteName")) {
    throw "IIS site '$SiteName' was not found."
}

$vdPath = "IIS:\Sites\$SiteName\$VirtualDir"
if (Test-Path $vdPath) {
    Set-ItemProperty -Path $vdPath -Name physicalPath -Value $WebRoot
} else {
    New-WebVirtualDirectory -Site $SiteName -Name $VirtualDir -PhysicalPath $WebRoot | Out-Null
}

# MIME types commonly needed
Add-IISMimeType -Extension ".ipxe" -MimeType "text/plain"
Add-IISMimeType -Extension ".wim"  -MimeType "application/octet-stream"
Add-IISMimeType -Extension ".sdi"  -MimeType "application/octet-stream"
Add-IISMimeType -Extension ".efi"  -MimeType "application/octet-stream"
Add-IISMimeType -Extension ".kpxe" -MimeType "application/octet-stream"
Add-IISMimeType -Extension ".bcd"  -MimeType "application/octet-stream"

Write-Host "== Opening firewall for HTTP =="
$fwName = "HTTP PXE IIS 80"
if (-not (Get-NetFirewallRule -DisplayName $fwName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $fwName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 80 | Out-Null
}

Write-Host ""
Write-Host "====================== DONE ======================"
Write-Host "Web root: $WebRoot"
Write-Host "PXE menu: http://$ServerIP/$VirtualDir/boot.ipxe"
Write-Host ""
Write-Host "IMPORTANT:"
Write-Host "1) Copy iPXE binaries into: $WebRoot"
Write-Host "   Required at minimum:"
Write-Host "   - wimboot"
Write-Host "   - undionly.kpxe (BIOS) and/or snponly.efi or ipxe.efi (UEFI)"
Write-Host ""
Write-Host "2) Point PXE clients to iPXE first, then chain to:"
Write-Host "   http://$ServerIP/$VirtualDir/boot.ipxe"
Write-Host ""
Write-Host "3) Files now being served:"
Write-Host "   http://$ServerIP/$VirtualDir/boot/boot.wim"
Write-Host "   http://$ServerIP/$VirtualDir/boot/boot.sdi"
Write-Host "   http://$ServerIP/$VirtualDir/boot/BCD"
Write-Host "   http://$ServerIP/$VirtualDir/boot/bootmgr"
Write-Host ""
Write-Host "4) Typical DHCP boot filenames:"
Write-Host "   BIOS  -> undionly.kpxe"
Write-Host "   UEFI  -> snponly.efi  (or ipxe.efi)"
Write-Host "================================================="