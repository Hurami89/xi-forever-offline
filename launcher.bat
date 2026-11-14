@echo off
rem Re-launch as administrator if needed (the game and Ashita need it on this setup)
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher.ps1"
echo.
echo Launcher finished. Press any key to close this window.
pause >nul
