param(
    [switch]$BootstrapNuGet
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$packagesConfig = Join-Path $repo "native\Gemini2API.WinUI\packages.config"
$packagesDirectory = Join-Path $repo "native\Gemini2API.WinUI\packages"
$localNuget = Join-Path $repo "native\.tools\nuget.exe"
$nugetSource = "https://api.nuget.org/v3/index.json"

$nuget = Get-Command nuget -ErrorAction SilentlyContinue
if (-not $nuget -and (Test-Path -LiteralPath $localNuget)) {
    $nuget = Get-Item -LiteralPath $localNuget
}

if (-not $nuget -and $BootstrapNuGet) {
    & (Join-Path $PSScriptRoot "bootstrap-nuget.ps1") -Destination $localNuget
    $nuget = Get-Item -LiteralPath $localNuget
}

if (-not $nuget) {
    throw "NuGet CLI is missing. Run native\scripts\bootstrap-nuget.ps1 or pass -BootstrapNuGet."
}

$nugetPath = if ($nuget.Source) { $nuget.Source } else { $nuget.FullName }
if (-not $nugetPath) {
    throw "Could not resolve NuGet CLI path."
}

New-Item -ItemType Directory -Force -Path $packagesDirectory | Out-Null
& $nugetPath restore $packagesConfig -PackagesDirectory $packagesDirectory -Source $nugetSource -NonInteractive
if ($LASTEXITCODE -ne 0) {
    throw "NuGet restore failed with exit code $LASTEXITCODE."
}

& (Join-Path $PSScriptRoot "verify-winui-packages-restored.ps1") -RequireRestored
Write-Host "[OK] WinUI NuGet packages restored to $packagesDirectory"
