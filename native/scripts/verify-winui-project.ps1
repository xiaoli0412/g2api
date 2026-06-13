$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$projectRoot = Join-Path $repo "native\Gemini2API.WinUI"
$projectPath = Join-Path $projectRoot "Gemini2API.WinUI.vcxproj"
$packagesPath = Join-Path $projectRoot "packages.config"
$solutionPath = Join-Path $projectRoot "Gemini2API.WinUI.sln"

foreach ($path in @($projectPath, $packagesPath, $solutionPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing required WinUI project file: $path"
    }
}

[xml]$project = Get-Content -LiteralPath $projectPath -Raw
[xml]$packages = Get-Content -LiteralPath $packagesPath -Raw

$ns = New-Object System.Xml.XmlNamespaceManager($project.NameTable)
$ns.AddNamespace("msb", "http://schemas.microsoft.com/developer/msbuild/2003")

$packageVersions = @{}
foreach ($package in $packages.packages.package) {
    $packageVersions[$package.id] = $package.version
}

$requiredPackages = @(
    "Microsoft.WindowsAppSDK",
    "Microsoft.Web.WebView2",
    "Microsoft.Windows.CppWinRT"
)

foreach ($id in $requiredPackages) {
    if (-not $packageVersions.ContainsKey($id)) {
        throw "packages.config missing $id"
    }
}

$projectText = Get-Content -LiteralPath $projectPath -Raw
foreach ($entry in $packageVersions.GetEnumerator() | Where-Object { $_.Key -in @("Microsoft.WindowsAppSDK", "Microsoft.Windows.CppWinRT") }) {
    $expectedFolder = "$($entry.Key).$($entry.Value)"
    if ($projectText -notmatch [regex]::Escape($expectedFolder)) {
        throw "Project does not import package folder $expectedFolder"
    }
}

foreach ($suffix in @(".props", ".targets")) {
    if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK$suffix")) {
        throw "Project missing Microsoft.WindowsAppSDK$suffix import"
    }
    if ($projectText -notmatch [regex]::Escape("Microsoft.Windows.CppWinRT$suffix")) {
        throw "Project missing Microsoft.Windows.CppWinRT$suffix import"
    }
}

foreach ($suffix in @(".props", ".targets")) {
    if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.WinUI$suffix")) {
        throw "Project missing Microsoft.WindowsAppSDK.WinUI$suffix import"
    }
}

if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.WinUI.2.1.0\metadata\Microsoft.UI.Xaml.winmd")) {
    throw "Project missing Microsoft.UI.Xaml WinMD reference."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.Foundation.2.0.21\metadata\Microsoft.Windows.ApplicationModel.Resources.winmd")) {
    throw "Project missing Microsoft.Windows.ApplicationModel.Resources WinMD reference."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.InteractiveExperiences.2.0.13\metadata\10.0.17763.0\Microsoft.UI.winmd")) {
    throw "Project missing Microsoft.UI WinMD reference."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.WinUI.2.1.0\metadata\Microsoft.UI.Text.winmd")) {
    throw "Project missing Microsoft.UI.Text WinMD reference."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.Web.WebView2.1.0.3967.48\lib\Microsoft.Web.WebView2.Core.winmd")) {
    throw "Project missing Microsoft.Web.WebView2.Core WinMD reference."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.Web.WebView2.1.0.3967.48\build\native\Microsoft.Web.WebView2.targets")) {
    throw "Project missing Microsoft.Web.WebView2 native targets import."
}
if ($projectText -notmatch [regex]::Escape("<WebView2UseWinRT>true</WebView2UseWinRT>")) {
    throw "Project must enable WebView2 WinRT metadata for WinUI."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppRuntime.Bootstrap.lib")) {
    throw "Project missing Windows App SDK bootstrap import library."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppRuntime.Bootstrap.dll")) {
    throw "Project missing Windows App SDK bootstrap DLL copy target."
}
if ($projectText -notmatch [regex]::Escape("Microsoft.WindowsAppSDK.Runtime.2.1.3\include")) {
    throw "Project missing Windows App SDK runtime include path."
}
if ($projectText -notmatch [regex]::Escape("/utf-8")) {
    throw "Project should compile native WinUI sources as UTF-8."
}

$mainText = Get-Content -LiteralPath (Join-Path $projectRoot "src\main.cpp") -Raw
if ($mainText -notmatch "MddBootstrap::Initialize") {
    throw "main.cpp must initialize the Windows App SDK runtime for unpackaged WinUI launch."
}

$includeNodes = $project.SelectNodes("//*[@Include]", $ns)
foreach ($node in $includeNodes) {
    if ($node.Name -eq "Reference") {
        continue
    }

    $include = $node.Include
    if ($include -and $include -notmatch "\|") {
        $full = Join-Path $projectRoot $include
        if (-not (Test-Path -LiteralPath $full)) {
            throw "Project references missing file: $include"
        }
    }
}

$viewNames = @(
    "HomePage",
    "ServerPage",
    "CookiesPage",
    "StreamingPage",
    "ModelsPage",
    "LogsPage",
    "SettingsPage"
)

foreach ($view in $viewNames) {
    foreach ($suffix in @(".xaml", ".idl", ".xaml.h", ".xaml.cpp")) {
        $path = Join-Path $projectRoot "src\Views\$view$suffix"
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Missing view file: src\Views\$view$suffix"
        }
    }

    if ($projectText -notmatch [regex]::Escape("src\Views\$view.xaml")) {
        throw "Project file missing XAML entry for $view"
    }
    if ($projectText -notmatch [regex]::Escape("src\Views\$view.idl")) {
        throw "Project file missing IDL entry for $view"
    }
}

$solutionText = Get-Content -LiteralPath $solutionPath -Raw
if ($solutionText -notmatch [regex]::Escape("Gemini2API.WinUI.vcxproj")) {
    throw "Solution does not reference Gemini2API.WinUI.vcxproj"
}

Write-Host "[OK] WinUI project/package consistency checks passed."
