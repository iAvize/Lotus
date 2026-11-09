@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Run-Lotus.ps1"
exit /b %ERRORLEVEL%
