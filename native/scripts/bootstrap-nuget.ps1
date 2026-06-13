param(
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $Destination) {
    $Destination = Join-Path $repo "native\.tools\nuget.exe"
}

$destinationDirectory = Split-Path -Parent $Destination
New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null

$url = "https://dist.nuget.org/win-x86-commandline/latest/nuget.exe"
Write-Host "[INFO] Downloading NuGet CLI from $url"
Invoke-WebRequest -Uri $url -OutFile $Destination

if (-not (Test-Path -LiteralPath $Destination)) {
    throw "NuGet download failed: $Destination"
}

& $Destination help | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Downloaded NuGet CLI did not run successfully."
}
Write-Host "[OK] NuGet CLI ready: $Destination"
