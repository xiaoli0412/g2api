$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$packagesPath = Join-Path $repo "native\Gemini2API.WinUI\packages.config"
[xml]$packages = Get-Content -LiteralPath $packagesPath -Raw

function Get-NuGetVersions {
    param(
        [string]$PackageId,
        [string]$IndexUrl
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            return (Invoke-RestMethod -Uri $IndexUrl -TimeoutSec 20).versions
        } catch {
            $lastError = $_.Exception.Message
            if ($attempt -lt 3) {
                Write-Host "[WARN] NuGet availability check retry $attempt for ${PackageId}: $lastError"
                Start-Sleep -Milliseconds (400 * $attempt)
            }
        }
    }

    throw "NuGet availability check failed for $PackageId after 3 attempts ($IndexUrl): $lastError"
}

foreach ($package in $packages.packages.package) {
    $id = [string]$package.id
    $version = [string]$package.version
    $flatId = $id.ToLowerInvariant()
    $indexUrl = "https://api.nuget.org/v3-flatcontainer/$flatId/index.json"
    $versions = Get-NuGetVersions -PackageId $id -IndexUrl $indexUrl

    if ($versions -notcontains $version) {
        throw "NuGet package $id version $version was not found on nuget.org"
    }

    $stable = $versions | Where-Object { $_ -notmatch "-" } | Select-Object -Last 1
    if ($stable -and $stable -ne $version) {
        Write-Host "[WARN] $id package uses $version; latest stable on nuget.org is $stable"
    } else {
        Write-Host "[OK]   $id $version exists on nuget.org"
    }
}

Write-Host "[OK] NuGet package availability checks passed."
