@echo off
cd /d "%~dp0\..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "native\scripts\run-winui.ps1"
