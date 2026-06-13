param(
    [string]$ToolsRoot = ""
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ToolsRoot) {
    $ToolsRoot = Join-Path $repo "native\.tools\rust"
}

$cargoHome = Join-Path $ToolsRoot "cargo"
$rustupHome = Join-Path $ToolsRoot "rustup"
$cargoBin = Join-Path $cargoHome "bin"
$cargoExe = Join-Path $cargoBin "cargo.exe"
$rustcExe = Join-Path $cargoBin "rustc.exe"
$rustupInit = Join-Path (Split-Path -Parent $ToolsRoot) "rustup-init.exe"

New-Item -ItemType Directory -Force -Path $cargoHome, $rustupHome | Out-Null

if (-not (Test-Path -LiteralPath $cargoExe)) {
    $url = "https://win.rustup.rs/x86_64"
    Write-Host "[INFO] Downloading rustup-init from $url"
    Invoke-WebRequest -Uri $url -OutFile $rustupInit

    $env:CARGO_HOME = $cargoHome
    $env:RUSTUP_HOME = $rustupHome
    & $rustupInit -y --no-modify-path --profile minimal --default-toolchain stable
    if ($LASTEXITCODE -ne 0) {
        throw "rustup-init failed with exit code $LASTEXITCODE."
    }
}

$env:CARGO_HOME = $cargoHome
$env:RUSTUP_HOME = $rustupHome

& $cargoExe --version
if ($LASTEXITCODE -ne 0) {
    throw "cargo did not run successfully."
}
& $rustcExe --version
if ($LASTEXITCODE -ne 0) {
    throw "rustc did not run successfully."
}

Write-Host "[OK] Local Rust toolchain ready: $cargoBin"
