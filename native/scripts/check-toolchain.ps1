$ErrorActionPreference = "Stop"

function Find-Command($Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Find-LocalTool($RelativePath) {
    $repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
    $full = Join-Path $repo $RelativePath
    if (Test-Path -LiteralPath $full) { return $full }
    return $null
}

function First-Value($Primary, $Fallback) {
    if ($Primary) { return $Primary }
    return $Fallback
}

function Find-VSInstallPath() {
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $vswhere) {
        $path = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
        if ($path) { return $path }
    }

    $fallback = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools"
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    return $null
}

function Find-VSTool($InstallPath, $Filter) {
    if (-not $InstallPath) { return $null }
    $tool = Get-ChildItem -LiteralPath $InstallPath -Recurse -Filter $Filter -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($tool) { return $tool.FullName }
    return $null
}

function Write-Check($Name, $Value) {
    if ($Value) {
        Write-Host "[OK]   $Name`: $Value"
    } else {
        Write-Host "[MISS] $Name"
    }
}

$vsInstallPath = Find-VSInstallPath

$checks = [ordered]@{
    "python" = Find-Command "python"
    "nuget" = First-Value (Find-Command "nuget") (Find-LocalTool "native\.tools\nuget.exe")
    "cargo" = First-Value (Find-Command "cargo") (Find-LocalTool "native\.tools\rust\cargo\bin\cargo.exe")
    "rustc" = First-Value (Find-Command "rustc") (Find-LocalTool "native\.tools\rust\cargo\bin\rustc.exe")
    "cmake" = Find-Command "cmake"
    "msbuild" = First-Value (Find-Command "msbuild") (Find-VSTool $vsInstallPath "MSBuild.exe")
    "cl" = First-Value (Find-Command "cl") (Find-VSTool $vsInstallPath "cl.exe")
}

foreach ($entry in $checks.GetEnumerator()) {
    Write-Check $entry.Key $entry.Value
}

$windowsKits = @(
    "${env:ProgramFiles(x86)}\Windows Kits\10",
    "${env:ProgramFiles}\Windows Kits\10"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
Write-Check "Windows SDK" ($windowsKits | Select-Object -First 1)

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path -LiteralPath $vswhere) {
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    Write-Check "Visual Studio C++ tools" $vs
} else {
    Write-Check "Visual Studio C++ tools" $vsInstallPath
}

Write-Host ""
Write-Host "Native build readiness:"
if ($checks["msbuild"] -or $checks["cl"]) {
    Write-Host "  C++/WinUI work can proceed after NuGet restore for native/Gemini2API.WinUI."
} else {
    Write-Host "  Install Visual Studio 2022 Build Tools with Desktop development with C++ and Windows App SDK."
    Write-Host "  Bootstrap helper: .\native\scripts\bootstrap-msvc-buildtools.ps1 -Install"
}

if ($checks["cargo"] -and $checks["rustc"] -and $checks["cl"]) {
    Write-Host "  Rust supervisor can be built with: cargo build --manifest-path native/supervisor-rs/Cargo.toml"
} elseif ($checks["cargo"] -and $checks["rustc"]) {
    Write-Host "  Rust supervisor can be type-checked with: .\native\scripts\check-supervisor.ps1"
    Write-Host "  Install Visual Studio C++ tools before cargo build/test on the MSVC Rust toolchain."
} else {
    Write-Host "  Install Rust from https://rustup.rs/ to build supervisor-rs."
}

if (-not $checks["nuget"]) {
    Write-Host "  Install NuGet CLI or use Visual Studio package restore before building the WinUI project."
}
