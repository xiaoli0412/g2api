@echo off
echo ============================================
echo   Gemini2API Desktop - Build Script
echo ============================================
echo.

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Python not found. Install Python 3.9+
    pause
    exit /b 1
)
echo [OK] Python found

echo.
echo [2/3] Installing dependencies...
pip install pyinstaller customtkinter pystray Pillow httpx tiktoken browser-cookie3 2>nul
if errorlevel 1 (
    echo [WARN] Some packages failed to install
)

echo.
echo [3/3] Building EXE...
python build.py
if errorlevel 1 (
    echo.
    echo [FAIL] Build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Output: dist\Gemini2API\Gemini2API.exe
echo ============================================
echo.
echo To create installer, install Inno Setup and run:
echo   iscc installer.iss
echo.
pause
