# One-time setup. Run in an elevated PowerShell:
#   cd C:\FFXISOLO ; Set-ExecutionPolicy -Scope Process Bypass ; .\setup.ps1
# Safe to re-run: anything already downloaded is skipped.
$ErrorActionPreference = "Continue"
$cfg = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$start = Get-Location

function Check($what) { if ($LASTEXITCODE -ne 0) { Set-Location $start; throw "FAILED: $what (exit code $LASTEXITCODE)" } }
function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "Missing '$cmd'. $hint" }
}
Need git    "Install Git for Windows."
Need cmake  "Install CMake and add it to PATH."
Need python "Install Python 3 and add it to PATH."
Need mysql  "Install MariaDB and add its bin folder to PATH."

# Find the Visual Studio C++ environment script (works for VS 2022 / 2026, Community or Build Tools)
$vcvars = $null
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
  $vs = & $vswhere -latest -products * -property installationPath
  if ($vs -and (Test-Path "$vs\VC\Auxiliary\Build\vcvarsall.bat")) { $vcvars = "$vs\VC\Auxiliary\Build\vcvarsall.bat" }
}
if (-not $vcvars) {
  $vcvars = (Get-ChildItem "C:\Program Files\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvarsall.bat","C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvarsall.bat" -ErrorAction SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $vcvars) { throw "Could not find the Visual Studio C++ tools. Open Visual Studio Installer and make sure 'Desktop development with C++' is installed." }
Write-Host "Using C++ tools: $vcvars" -ForegroundColor DarkGray

New-Item -ItemType Directory -Force (Split-Path $cfg.server_dir) | Out-Null
if (-not (Test-Path $cfg.server_dir))   { git clone --recursive $cfg.repo $cfg.server_dir; Check "clone Phoenix" }
if (-not (Test-Path $cfg.xiloader_dir)) { git clone --recursive $cfg.xiloader_repo $cfg.xiloader_dir; Check "clone xiloader" }
if (-not (Test-Path $cfg.era_dats_dir)) { git clone $cfg.era_dats_repo $cfg.era_dats_dir; Check "clone Era-DATs" }

Write-Host "`n=== Python packages ===" -ForegroundColor Cyan
Set-Location $cfg.server_dir
python -m pip install -r tools/requirements.txt
Check "pip install"
Set-Location $start

# Parallel compile jobs. Lower this (e.g. 2) if you get "out of heap space" errors; raise it if your PC has lots of RAM.
$jobs = if ($cfg.build_jobs) { $cfg.build_jobs } else { 4 }

# Builds inside the Visual Studio environment (arch: x64 for the server, x86 for xiloader because the game is 32-bit)
function BuildIn($dir, $arch, $label) {
  $bat = Join-Path $env:TEMP "build_$label.bat"
  @"
@echo off
call "$vcvars" $arch
if errorlevel 1 exit /b 1
cd /d "$dir"
set GEN=NMake Makefiles
where ninja >nul 2>nul && set GEN=Ninja
echo Using generator: %GEN%
cmake -S . -B build -G "%GEN%" -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b 1
cmake --build build -j $jobs
if errorlevel 1 exit /b 1
"@ | Set-Content -Encoding ASCII $bat
  cmd /c $bat
  Check "build $label"
}

Write-Host "`n=== Building server (this is the slow part) ===" -ForegroundColor Cyan
BuildIn $cfg.server_dir "x64" "server"

Write-Host "`n=== Building xiloader (32-bit) ===" -ForegroundColor Cyan
BuildIn $cfg.xiloader_dir "x86" "xiloader"

Write-Host "`nBUILD FINISHED." -ForegroundColor Green
Write-Host "Next: database. Tell Claude the build finished and we'll do it step by step."
