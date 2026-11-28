# Builds "XI Forever Offline Setup.exe" in dist\: the one file a new player downloads (installer\xifo_setup.py).
# It downloads the newest release, unpacks it, makes the shortcuts and opens the launcher. The launcher updates itself
# afterwards, so the same Setup.exe keeps working for later versions; build it again only when xifo_setup.py changes.
# Run in PowerShell:  cd C:\FFXISOLO ; Set-ExecutionPolicy -Scope Process Bypass ; .\build_installer.ps1
# Uses the same private Python as build_release.ps1 (build\venv); run that once first if build\venv is missing.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = Join-Path $PSScriptRoot "build\venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "build\venv is missing: run .\build_release.ps1 once first (it makes the build environment)." }

$icon = Join-Path $PSScriptRoot "assets\ui\icon.ico"
$png = Join-Path $PSScriptRoot "assets\ui\icon.png"
$dist = Join-Path $PSScriptRoot "dist"
$opts = @("--noconfirm", "--onefile", "--windowed", "--name", "XI Forever Offline Setup", "--icon", $icon,
          "--add-data", "$icon;.", "--add-data", "$png;.",
          "--hidden-import", "PIL.Image", "--hidden-import", "PIL.ImageTk", "--collect-data", "certifi",
          "--distpath", $dist, "--workpath", (Join-Path $PSScriptRoot "build\installer"),
          "--specpath", (Join-Path $PSScriptRoot "build\installer"))
& $py -m PyInstaller @opts (Join-Path $PSScriptRoot "installer\xifo_setup.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Write-Host "`nBuilt: $(Join-Path $dist 'XI Forever Offline Setup.exe')" -ForegroundColor Green
Write-Host "The next publish uploads it to the release as XI-Forever-Offline-Setup.exe." -ForegroundColor DarkGray
