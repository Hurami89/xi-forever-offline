# Rebuilds the server after code changes (much faster than setup.ps1: only changed files recompile).
# Run in an ADMINISTRATOR PowerShell:  cd C:\FFXISOLO ; Set-ExecutionPolicy -Scope Process Bypass ; .\rebuild.ps1
# Add -Reconfigure if new .cpp files were added.
param([switch]$Reconfigure)
$ErrorActionPreference = "Continue"
$cfg = Get-Content "$PSScriptRoot\config.json" | ConvertFrom-Json
$jobs = if ($cfg.build_jobs) { $cfg.build_jobs } else { 4 }

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -property installationPath
$vcvars = "$vs\VC\Auxiliary\Build\vcvarsall.bat"
if (-not (Test-Path $vcvars)) { throw "Visual Studio C++ tools not found." }

# Stop the servers first so the .exe files are not locked
Get-Process xi_connect,xi_world,xi_search,xi_profile,xi_map -ErrorAction SilentlyContinue | Stop-Process -Force

$bat = Join-Path $env:TEMP "rebuild_server.bat"
$cfgLine = if ($Reconfigure) { 'cmake -S . -B build -G "%GEN%" -DCMAKE_BUILD_TYPE=Release' } else { 'rem (no reconfigure)' }
@"
@echo off
call "$vcvars" x64
if errorlevel 1 exit /b 1
cd /d "$($cfg.server_dir)"
set GEN=NMake Makefiles
where ninja >nul 2>nul && set GEN=Ninja
$cfgLine
cmake --build build -j $jobs
"@ | Set-Content -Encoding ASCII $bat
cmd /c $bat
if ($LASTEXITCODE -ne 0) { Write-Host "`nBUILD FAILED - send Claude the last 15 lines above." -ForegroundColor Red; exit 1 }
Write-Host "`nBUILD FINISHED." -ForegroundColor Green
