param(
    [switch]$BuildWhenPossible,
    [switch]$RunVisual,
    [switch]$RunWebVisual,
    [switch]$ExerciseBackendControls
)

$ErrorActionPreference = "Stop"

$scripts = @(
    "verify-native-layout.ps1",
    "verify-winui-markup.ps1",
    "verify-winui-project.ps1",
    "verify-native-source.ps1",
    "verify-rust-source.ps1",
    "verify-nuget-packages.ps1",
    "verify-winui-packages-restored.ps1",
    "check-supervisor.ps1",
    "check-toolchain.ps1"
)

foreach ($script in $scripts) {
    & (Join-Path $PSScriptRoot $script)
}

if ($BuildWhenPossible) {
    & (Join-Path $PSScriptRoot "build-winui.ps1")
    & (Join-Path $PSScriptRoot "build-supervisor.ps1")
}

if ($RunVisual) {
    $runtimeArgs = @{
        ExerciseLanguageToggle = $true
    }
    if ($ExerciseBackendControls) {
        $runtimeArgs.ExerciseBackendControls = $true
    }
    & (Join-Path $PSScriptRoot "verify-winui-runtime.ps1") @runtimeArgs
}

if ($RunWebVisual) {
    & (Join-Path $PSScriptRoot "verify-web-dashboard-runtime.ps1")
}

Write-Host "[OK] All available native verification checks completed."
