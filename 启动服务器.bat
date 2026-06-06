@echo off
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=python
) else if exist "C:\Users\李昊桐\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe" (
    set PYTHON="C:\Users\李昊桐\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe"
) else (
    echo Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

echo Starting Gemini Web2API Server...
echo URL: http://localhost:8081/v1
echo ============================================

%PYTHON% gemini_web2api.py

if %errorlevel% neq 0 (
    echo.
    echo Server exited with error: %errorlevel%
    pause
)
