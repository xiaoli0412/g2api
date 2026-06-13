param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidateSet("x64")]
    [string]$Platform = "x64",
    [switch]$RequireToolchain
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$solution = Join-Path $repo "native\Gemini2API.WinUI\Gemini2API.WinUI.sln"
$localNuget = Join-Path $repo "native\.tools\nuget.exe"
$vsDevCmd = & (Join-Path $PSScriptRoot "find-vsdevcmd.ps1")

$nuget = Get-Command nuget -ErrorAction SilentlyContinue
if (-not $nuget -and (Test-Path -LiteralPath $localNuget)) {
    $nuget = Get-Item -LiteralPath $localNuget
}

if (-not $nuget) {
    & (Join-Path $PSScriptRoot "restore-winui-packages.ps1") -BootstrapNuGet
} else {
    & (Join-Path $PSScriptRoot "restore-winui-packages.ps1")
}

$command = "`"$vsDevCmd`" -no_logo -arch=$Platform -host_arch=x64 && msbuild `"$solution`" /m /p:Configuration=$Configuration /p:Platform=$Platform"
& cmd.exe /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw "WinUI build failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] WinUI build completed for $Configuration|$Platform."
