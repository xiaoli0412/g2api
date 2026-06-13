param(
    [int]$Port = 18183,
    [int]$TimeoutSeconds = 20
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

if (-not $cargo) {
    Write-Host "[SKIP] Rust toolchain is not installed; supervisor smoke test cannot build."
    exit 0
}

if ((Test-Path -LiteralPath $localCargo) -and ($cargo.FullName -eq $localCargo)) {
    $env:CARGO_HOME = $localCargoHome
    $env:RUSTUP_HOME = $localRustupHome
}

$cargoPath = if ($cargo.Source) { $cargo.Source } else { $cargo.FullName }

function Test-BackendReachable {
    param([int]$CheckPort)

    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$CheckPort/" -UseBasicParsing -TimeoutSec 1
        return $resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-BackendStopped {
    param(
        [int]$CheckPort,
        [int]$TimeoutMilliseconds = 10000
    )

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (-not (Test-BackendReachable -CheckPort $CheckPort)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "Supervisor smoke test left backend reachable on 127.0.0.1:$CheckPort."
}

Push-Location $repo
try {
    if (Test-BackendReachable -CheckPort $Port) {
        throw "Supervisor smoke test refused to run because 127.0.0.1:$Port is already reachable."
    }

    & $cargoPath test --manifest-path $manifest
    if ($LASTEXITCODE -ne 0) {
        throw "Rust supervisor tests failed with exit code $LASTEXITCODE."
    }

    & $cargoPath run --manifest-path $manifest -- probe $Port /
    if ($LASTEXITCODE -ne 0) {
        throw "Rust supervisor probe command failed with exit code $LASTEXITCODE."
    }

    $tempRoot = Join-Path $env:TEMP ("gemini2api_supervisor_smoke_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $configPath = Join-Path $tempRoot "config.json"
    try {
        $config = [ordered]@{
            port = $Port
            host = "127.0.0.1"
            default_model = "gemini-3.5-flash"
            api_keys = @()
            cookie_file = $null
            proxy = $null
            log_requests = $false
        }
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 8), $utf8NoBom)

        $startOutput = & $cargoPath run --manifest-path $manifest -- start python $configPath $Port $TimeoutSeconds
        if ($LASTEXITCODE -ne 0) {
            throw "Rust supervisor start smoke failed with exit code $LASTEXITCODE."
        }

        $reportLine = $startOutput | Where-Object { $_ -match '^\{' } | Select-Object -First 1
        if (-not $reportLine) {
            throw "Rust supervisor start smoke did not emit a JSON report."
        }

        $report = $reportLine | ConvertFrom-Json
        if (-not $report.started -or -not $report.health.ready) {
            throw "Rust supervisor start smoke did not report a ready backend: $reportLine"
        }

        Wait-BackendStopped -CheckPort $Port
        Write-Host "[OK] Rust supervisor smoke test started and cleaned backend on 127.0.0.1:$Port"
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
} finally {
    Pop-Location
}
