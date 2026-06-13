param(
    [switch]$BootstrapRust,
    [switch]$RequireToolchain
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$manifest = Join-Path $repo "native\supervisor-rs\Cargo.toml"
$localCargoHome = Join-Path $repo "native\.tools\rust\cargo"
$localRustupHome = Join-Path $repo "native\.tools\rust\rustup"
$localCargo = Join-Path $localCargoHome "bin\cargo.exe"

$cargo = Get-Command cargo -ErrorAction SilentlyContinue
if (-not $cargo -and (Test-Path -LiteralPath $localCargo)) {
    $cargo = Get-Item -LiteralPath $localCargo
}

if (-not $cargo -and $BootstrapRust) {
    & (Join-Path $PSScriptRoot "bootstrap-rust.ps1")
    $cargo = Get-Item -LiteralPath $localCargo
}

if (-not $cargo) {
    if ($RequireToolchain) {
        throw "Cargo is missing."
    }

    Write-Host "[SKIP] Rust supervisor cargo check skipped: cargo missing."
    exit 0
}

if ((Test-Path -LiteralPath $localCargo) -and ($cargo.FullName -eq $localCargo)) {
    $env:CARGO_HOME = $localCargoHome
    $env:RUSTUP_HOME = $localRustupHome
}

$cargoPath = if ($cargo.Source) { $cargo.Source } else { $cargo.FullName }
& $cargoPath check --manifest-path $manifest
if ($LASTEXITCODE -ne 0) {
    throw "Rust supervisor cargo check failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] Rust supervisor cargo check passed."
