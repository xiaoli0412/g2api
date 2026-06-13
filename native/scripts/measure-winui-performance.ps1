param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [ValidateSet("x64")]
    [string]$Platform = "x64",
    [string]$ExePath,
    [string]$OutputDirectory,
    [int]$SampleSeconds = 8,
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $ExePath) {
    $ExePath = Join-Path $repo "build\native\$Platform\$Configuration\Gemini2API.WinUI.exe"
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repo "output\native-visual"
}

if ($Build) {
    & (Join-Path $PSScriptRoot "build-winui.ps1") -Configuration $Configuration -Platform $Platform
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Missing WinUI executable: $ExePath. Run native\scripts\build-winui.ps1 first."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$process = $null
try {
    $process = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath) -PassThru -WindowStyle Normal
    Start-Sleep -Milliseconds 1200
    $process.Refresh()
    if ($process.HasExited) {
        throw "WinUI process exited during performance sampling with code $($process.ExitCode)."
    }

    $samples = New-Object "System.Collections.Generic.List[object]"
    $lastCpu = $process.CPU
    $lastTime = [DateTime]::UtcNow
    for ($i = 0; $i -lt $SampleSeconds; $i++) {
        Start-Sleep -Seconds 1
        $process.Refresh()
        if ($process.HasExited) {
            throw "WinUI process exited during performance sampling with code $($process.ExitCode)."
        }

        $now = [DateTime]::UtcNow
        $cpu = $process.CPU
        $elapsed = [Math]::Max(0.001, ($now - $lastTime).TotalSeconds)
        $cpuPercentOneCore = [Math]::Round((($cpu - $lastCpu) / $elapsed) * 100.0, 2)
        $samples.Add([pscustomobject]@{
            second = $i + 1
            cpu_percent_one_core = $cpuPercentOneCore
            working_set_mb = [Math]::Round($process.WorkingSet64 / 1MB, 2)
            private_memory_mb = [Math]::Round($process.PrivateMemorySize64 / 1MB, 2)
        })
        $lastCpu = $cpu
        $lastTime = $now
    }

    $avgCpu = [Math]::Round((($samples | Measure-Object -Property cpu_percent_one_core -Average).Average), 2)
    $maxCpu = [Math]::Round((($samples | Measure-Object -Property cpu_percent_one_core -Maximum).Maximum), 2)
    $maxWorkingSet = [Math]::Round((($samples | Measure-Object -Property working_set_mb -Maximum).Maximum), 2)
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $path = Join-Path $OutputDirectory "winui-performance-$stamp.json"
    [ordered]@{
        executable = (Resolve-Path -LiteralPath $ExePath).Path
        configuration = $Configuration
        sample_seconds = $SampleSeconds
        average_cpu_percent_one_core = $avgCpu
        max_cpu_percent_one_core = $maxCpu
        max_working_set_mb = $maxWorkingSet
        samples = $samples
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $path -Encoding UTF8

    Write-Host ("[OK] WinUI performance sampled: avg_cpu_one_core={0}%, max_cpu_one_core={1}%, max_working_set={2} MB" -f $avgCpu, $maxCpu, $maxWorkingSet)
    Write-Host "[OK] Performance metrics: $path"
} finally {
    if ($process) {
        $process.Refresh()
        if (-not $process.HasExited) {
            [void]$process.CloseMainWindow()
            if (-not $process.WaitForExit(3000)) {
                Stop-Process -Id $process.Id -Force
            }
        }
    }
}
