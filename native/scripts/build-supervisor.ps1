param(
    [switch]$Release,
    [switch]$RequireToolchain
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$manifest = Join-Path $repo "native\supervisor-rs\Cargo.toml"
$localCargoHome = Join-Path $repo "native\.tools\rust\cargo"
$localRustupHome = Join-Path $repo "native\.tools\rust\rustup"
$localCargo = Join-Path $localCargoHome "bin\cargo.exe"
$vsDevCmd = & (Join-Path $PSScriptRoot "find-vsdevcmd.ps1")
$cargo = Get-Command cargo -ErrorAction SilentlyContinue
if (-not $cargo -and (Test-Path -LiteralPath $localCargo)) {
    $cargo = Get-Item -LiteralPath $localCargo
}

if (-not $cargo) {
    if ($RequireToolchain) {
        throw "Rust supervisor build requires cargo, but cargo is missing."
    }

    Write-Host "[SKIP] Rust supervisor build skipped: cargo missing."
    exit 0
}

if ((Test-Path -LiteralPath $localCargo) -and ($cargo.FullName -eq $localCargo)) {
    $env:CARGO_HOME = $localCargoHome
    $env:RUSTUP_HOME = $localRustupHome
}

$cargoArgs = @("build", "--manifest-path", $manifest)
if ($Release) {
    $cargoArgs += "--release"
}

$cargoPath = if ($cargo.Source) { $cargo.Source } else { $cargo.FullName }
$testCommand = "`"$vsDevCmd`" -no_logo -arch=x64 -host_arch=x64 && `"$cargoPath`" test --manifest-path `"$manifest`""
& cmd.exe /s /c $testCommand
if ($LASTEXITCODE -ne 0) {
    throw "Rust supervisor tests failed with exit code $LASTEXITCODE."
}
$buildTail = ($cargoArgs | ForEach-Object { "`"$_`"" }) -join " "
$buildCommand = "`"$vsDevCmd`" -no_logo -arch=x64 -host_arch=x64 && `"$cargoPath`" $buildTail"
& cmd.exe /s /c $buildCommand
if ($LASTEXITCODE -ne 0) {
    throw "Rust supervisor build failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] Rust supervisor build completed."
