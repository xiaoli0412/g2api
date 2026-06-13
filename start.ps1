$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

$pythonPath = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonPath = "python"
} elseif (Test-Path "C:\Users\李昊桐\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe") {
    $pythonPath = "C:\Users\李昊桐\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe"
} else {
    Write-Host "Python not found. Please install Python 3.8+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting Gemini Web2API Server..." -ForegroundColor Green
Write-Host "URL: http://localhost:8081/v1" -ForegroundColor Cyan
if (Test-Path "cookie.txt") {
    Write-Host "Cookie: YES (Pro model available)" -ForegroundColor Green
} else {
    Write-Host "Cookie: NO (anonymous mode)" -ForegroundColor Yellow
}
Write-Host "========================================" -ForegroundColor Yellow

& $pythonPath gemini_web2api.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Server exited with error: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
