param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    throw "winget is missing. Install Visual Studio 2022 Build Tools manually from Microsoft."
}

$packageId = "Microsoft.VisualStudio.2022.BuildTools"
$override = "--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.NativeDesktop --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.26100 --includeRecommended"

Write-Host "[INFO] Required package: $packageId"
Write-Host "[INFO] Required components: Native Desktop workload, MSVC x64/x86 tools, Windows 11 SDK 26100"

if (-not $Install) {
    Write-Host "[INFO] Dry run only. To install, run:"
    Write-Host "       .\native\scripts\bootstrap-msvc-buildtools.ps1 -Install"
    exit 0
}

& winget install --id $packageId --exact --silent --accept-source-agreements --accept-package-agreements --override $override
if ($LASTEXITCODE -ne 0) {
    throw "winget Visual Studio Build Tools install failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] Visual Studio Build Tools installation command completed. Restart the shell before building if PATH was updated."
