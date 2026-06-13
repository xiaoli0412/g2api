param(
    [switch]$RequireRestored
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$projectRoot = Join-Path $repo "native\Gemini2API.WinUI"
$packagesPath = Join-Path $projectRoot "packages.config"
$packagesDirectory = Join-Path $projectRoot "packages"

if (-not (Test-Path -LiteralPath $packagesDirectory)) {
    if ($RequireRestored) {
        throw "WinUI packages directory is missing: $packagesDirectory"
    }

    Write-Host "[SKIP] WinUI packages are not restored yet."
    exit 0
}

[xml]$packages = Get-Content -LiteralPath $packagesPath -Raw
foreach ($package in $packages.packages.package) {
    $folder = Join-Path $packagesDirectory "$($package.id).$($package.version)"
    if (-not (Test-Path -LiteralPath $folder)) {
        throw "Restored package folder missing: $folder"
    }

    if ($package.id -in @("Microsoft.WindowsAppSDK", "Microsoft.Windows.CppWinRT")) {
        foreach ($suffix in @(".props", ".targets")) {
            $fileName = "$($package.id)$suffix"
            $path = Join-Path $folder "build\native\$fileName"
            if (-not (Test-Path -LiteralPath $path)) {
                throw "Restored package build file missing: $path"
            }
        }
    }

    if ($package.id -eq "Microsoft.WindowsAppSDK.WinUI") {
        foreach ($suffix in @(".props", ".targets")) {
            $fileName = "$($package.id)$suffix"
            $path = Join-Path $folder "buildTransitive\native\$fileName"
            if (-not (Test-Path -LiteralPath $path)) {
                throw "Restored package build file missing: $path"
            }
        }
    }

    if ($package.id -eq "Microsoft.Web.WebView2") {
        $targetsPath = Join-Path $folder "build\native\Microsoft.Web.WebView2.targets"
        if (-not (Test-Path -LiteralPath $targetsPath)) {
            throw "Restored package build file missing: $targetsPath"
        }

        $winmdPath = Join-Path $folder "lib\Microsoft.Web.WebView2.Core.winmd"
        if (-not (Test-Path -LiteralPath $winmdPath)) {
            throw "Restored package WinMD missing: $winmdPath"
        }
    }

    Write-Host "[OK] Restored package present: $($package.id) $($package.version)"
}

Write-Host "[OK] Restored WinUI package contents are present."
