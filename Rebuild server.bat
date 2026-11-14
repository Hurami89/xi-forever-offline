@echo off
title Rebuild XI: Forever Offline server
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rebuild.ps1"
echo.
echo You can close this window now.
pause
