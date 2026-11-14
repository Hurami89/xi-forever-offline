@echo off
title Rebuild FFXI Offline server
cd /d C:\FFXISOLO
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\FFXISOLO\rebuild.ps1"
echo.
echo You can close this window now.
pause
