$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$xamlFiles = Get-ChildItem -LiteralPath (Join-Path $repo "native\Gemini2API.WinUI\src") -Recurse -Filter *.xaml

foreach ($file in $xamlFiles) {
    try {
        [xml]$null = Get-Content -LiteralPath $file.FullName -Raw
        Write-Host "[OK] XAML parses: $($file.FullName.Substring($repo.Path.Length + 1))"
    } catch {
        throw "XAML XML parse failed for $($file.FullName): $($_.Exception.Message)"
    }
}

$main = Get-Content -LiteralPath (Join-Path $repo "native\Gemini2API.WinUI\src\MainWindow.xaml") -Raw
foreach ($required in @("Segoe Fluent Icons", "NavigationView", "PersonalBackgroundImage")) {
    if ($main -notmatch [regex]::Escape($required)) {
        throw "MainWindow.xaml missing $required"
    }
}

foreach ($removedSearchPattern in @("AutoSuggestBox", "QueryIcon=", "SearchBox", "Search settings", "Search models")) {
    if ($main -match [regex]::Escape($removedSearchPattern)) {
        throw "Search UI was removed and must not come back: $removedSearchPattern"
    }
}

Write-Host "[OK] WinUI markup checks passed."
