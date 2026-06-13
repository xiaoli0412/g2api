$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$manifest = Join-Path $repo "native\supervisor-rs\Cargo.toml"
$main = Join-Path $repo "native\supervisor-rs\src\main.rs"

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Missing Rust manifest: $manifest"
}
if (-not (Test-Path -LiteralPath $main)) {
    throw "Missing Rust supervisor source: $main"
}

$manifestText = Get-Content -LiteralPath $manifest -Raw
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($dependency in @("anyhow", "serde", "serde_json", "ureq", "windows")) {
    if ($manifestText -match $dependency) {
        throw "Cargo.toml should stay dependency-free, but found $dependency"
    }
}

foreach ($command in @('"probe"', '"status"', '"start"', '"run"')) {
    if ($mainText -notmatch [regex]::Escape($command)) {
        throw "Rust supervisor missing command $command"
    }
}

foreach ($endpoint in @('"/"', '"/v1/models"', '"/admin"', '"/admin/stats"')) {
    if ($mainText -notmatch [regex]::Escape($endpoint)) {
        throw "Rust supervisor missing endpoint $endpoint"
    }
}

foreach ($shape in @("ProbeResult", "BackendHealth", "StartReport", "ExitReport")) {
    if ($mainText -notmatch $shape) {
        throw "Rust supervisor missing JSON shape $shape"
    }
}

foreach ($stdFeature in @("TcpStream", "SocketAddr", "Command::new")) {
    if ($mainText -notmatch [regex]::Escape($stdFeature)) {
        throw "Rust supervisor missing standard-library feature $stdFeature"
    }
}

foreach ($jobPattern in @(
    "ManagedChild",
    "CreateJobObjectW",
    "SetInformationJobObject",
    "AssignProcessToJobObject",
    "TerminateJobObject",
    "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
    "CREATE_NO_WINDOW",
    "child.terminate()"
)) {
    if ($mainText -notmatch [regex]::Escape($jobPattern)) {
        throw "Rust supervisor missing Windows process-tree guard: $jobPattern"
    }
}

Write-Host "[OK] Rust supervisor source consistency checks passed."
