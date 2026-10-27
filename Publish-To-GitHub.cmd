@echo off
echo BGP Routing Laboratory - Publish to GitHub
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Publish-To-GitHub.ps1"
echo.
pause
