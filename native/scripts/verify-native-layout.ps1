$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$required = @(
    "native\README.md",
    "native\contracts\backend-api.md",
    "native\Gemini2API.WinUI\README.md",
    "native\Gemini2API.WinUI\Gemini2API.WinUI.sln",
    "native\Gemini2API.WinUI\Gemini2API.WinUI.vcxproj",
    "native\Gemini2API.WinUI\packages.config",
    "native\Gemini2API.WinUI\src\App.xaml",
    "native\Gemini2API.WinUI\src\App.xaml.h",
    "native\Gemini2API.WinUI\src\App.xaml.cpp",
    "native\Gemini2API.WinUI\src\App.idl",
    "native\Gemini2API.WinUI\src\MainWindow.xaml",
    "native\Gemini2API.WinUI\src\MainWindow.xaml.h",
    "native\Gemini2API.WinUI\src\MainWindow.xaml.cpp",
    "native\Gemini2API.WinUI\src\MainWindow.idl",
    "native\Gemini2API.WinUI\src\NativeLog.h",
    "native\Gemini2API.WinUI\src\Styles\NativeTheme.xaml",
    "native\Gemini2API.WinUI\src\Views\HomePage.xaml",
    "native\Gemini2API.WinUI\src\Views\ServerPage.xaml",
    "native\Gemini2API.WinUI\src\Views\CookiesPage.xaml",
    "native\Gemini2API.WinUI\src\Views\StreamingPage.xaml",
    "native\Gemini2API.WinUI\src\Views\ModelsPage.xaml",
    "native\Gemini2API.WinUI\src\Views\LogsPage.xaml",
    "native\Gemini2API.WinUI\src\Views\SettingsPage.xaml",
    "native\Gemini2API.WinUI\src\BackendClient.h",
    "native\Gemini2API.WinUI\src\BackendClient.cpp",
    "native\Gemini2API.WinUI\src\BackendProcess.h",
    "native\Gemini2API.WinUI\src\BackendProcess.cpp",
    "native\scripts\check-toolchain.ps1",
    "native\scripts\build-winui.ps1",
    "native\scripts\build-supervisor.ps1",
    "native\scripts\bootstrap-msvc-buildtools.ps1",
    "native\scripts\bootstrap-nuget.ps1",
    "native\scripts\bootstrap-rust.ps1",
    "native\scripts\check-supervisor.ps1",
    "native\scripts\find-vsdevcmd.ps1",
    "native\scripts\restore-winui-packages.ps1",
    "native\scripts\smoke-backend.ps1",
    "native\scripts\smoke-supervisor.ps1",
    "native\scripts\verify-all-native.ps1",
    "native\scripts\verify-winui-runtime.ps1",
    "native\scripts\measure-winui-performance.ps1",
    "native\scripts\verify-native-layout.ps1",
    "native\scripts\verify-winui-markup.ps1",
    "native\scripts\verify-winui-project.ps1",
    "native\scripts\verify-native-source.ps1",
    "native\scripts\verify-rust-source.ps1",
    "native\scripts\verify-nuget-packages.ps1",
    "native\scripts\verify-winui-packages-restored.ps1",
    "native\supervisor-rs\Cargo.toml",
    "native\supervisor-rs\src\main.rs"
)

foreach ($path in $required) {
    $full = Join-Path $repo $path
    if (-not (Test-Path -LiteralPath $full)) {
        throw "Missing required native file: $path"
    }
}

function Assert-Contains($Path, $Pattern, $Description) {
    $full = Join-Path $repo $Path
    $text = Get-Content -LiteralPath $full -Raw
    if ($text -notmatch $Pattern) {
        throw "Missing $Description in $Path"
    }
}

Assert-Contains "native\Gemini2API.WinUI\src\MainWindow.xaml.cpp" "MicaBackdrop" "Mica system backdrop"
Assert-Contains "native\Gemini2API.WinUI\src\MainWindow.xaml.cpp" "ExtendsContentIntoTitleBar" "custom title bar integration"
Assert-Contains "native\Gemini2API.WinUI\src\MainWindow.xaml" "NavigationView" "WinUI NavigationView shell"
Assert-Contains "native\Gemini2API.WinUI\src\Views\CookiesPage.xaml" "MenuFlyout" "native context menu"
Assert-Contains "native\Gemini2API.WinUI\src\BackendClient.cpp" "WinHttpOpen" "WinHTTP backend client"
Assert-Contains "native\Gemini2API.WinUI\src\BackendProcess.cpp" "CreateProcessW" "Windows process launch"
Assert-Contains "native\supervisor-rs\src\main.rs" "/admin/stats" "admin stats health probe"

Write-Host "[OK] Native layout files and required Windows-native patterns are present."
