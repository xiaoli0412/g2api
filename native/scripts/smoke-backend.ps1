param(
    [int]$Port = 18081,
    [int]$TimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$tempRoot = Join-Path $env:TEMP ("gemini2api_native_smoke_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$configPath = Join-Path $tempRoot "config.json"

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

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "python"
$psi.Arguments = ('-m gemini_web2api --config "{0}" --port {1}' -f $configPath.Replace('"', '\"'), $Port)
$psi.WorkingDirectory = $repo
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$proc = [System.Diagnostics.Process]::Start($psi)

try {
    $base = "http://127.0.0.1:$Port"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $root = Invoke-RestMethod -Uri "$base/" -TimeoutSec 2
            if ($root.status -eq "ok") {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }

    if (-not $ready) {
        $stdout = $proc.StandardOutput.ReadToEnd()
        $stderr = $proc.StandardError.ReadToEnd()
        throw "Backend did not become ready. stdout=$stdout stderr=$stderr"
    }

    $models = Invoke-RestMethod -Uri "$base/v1/models" -TimeoutSec 5
    $admin = Invoke-RestMethod -Uri "$base/admin" -TimeoutSec 5
    $stats = Invoke-RestMethod -Uri "$base/admin/stats" -TimeoutSec 5

    if (-not $models.data) { throw "Model list is empty or malformed." }
    if ($admin.status -ne "ok") { throw "Admin endpoint did not return ok." }
    if ($null -eq $stats.total_requests) { throw "Admin stats missing total_requests." }

    Write-Host "[OK] Backend smoke test passed on $base"
    Write-Host "     models: $($models.data.Count)"
    Write-Host "     admin endpoints: $($admin.endpoints.Count)"
} finally {
    if ($proc -and -not $proc.HasExited) {
        $proc.Kill()
        $proc.WaitForExit(5000) | Out-Null
    }
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
