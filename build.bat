@echo off
setlocal
echo ============================================
echo   Gemini2API Native WinUI + Rust Supervisor Build
echo ============================================
echo.

cd /d "%~dp0"
rem build.py orchestrates native\scripts\build-winui.ps1 and native\scripts\build-supervisor.ps1.
python "%~dp0build.py"
if errorlevel 1 (
    echo.
    echo [FAIL] Native WinUI + Rust supervisor build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Output: build\native\x64\Release\Gemini2API.WinUI.exe
echo   Helper: build\native\x64\Release\gemini2api-supervisor.exe
echo   Run:    run-gui.bat
echo ============================================
echo.
pause
