$ErrorActionPreference = "Stop"

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$src = Join-Path $repo "native\Gemini2API.WinUI\src"

function Read-Text($RelativePath) {
    Get-Content -LiteralPath (Join-Path $src $RelativePath) -Raw
}

$mainWindowCpp = Read-Text "MainWindow.xaml.cpp"
$mainWindowHeader = Read-Text "MainWindow.xaml.h"
$mainWindowXaml = Read-Text "MainWindow.xaml"
$modelsPageXaml = Read-Text "Views\ModelsPage.xaml"
$mainCpp = Read-Text "main.cpp"
$backendClientCpp = Read-Text "BackendClient.cpp"
$backendProcessCpp = Read-Text "BackendProcess.cpp"
$projectFile = Get-Content -LiteralPath (Join-Path $repo "native\Gemini2API.WinUI\Gemini2API.WinUI.vcxproj") -Raw
$manifestFile = Get-Content -LiteralPath (Join-Path $src "app.manifest") -Raw
$rootLauncher = Get-Content -LiteralPath (Join-Path $repo "run-gui.bat") -Raw
$nativeLauncher = Get-Content -LiteralPath (Join-Path $repo "native\scripts\run-winui.ps1") -Raw
$rootBuildBat = Get-Content -LiteralPath (Join-Path $repo "build.bat") -Raw
$rootBuildPy = Get-Content -LiteralPath (Join-Path $repo "build.py") -Raw
$installerScript = Get-Content -LiteralPath (Join-Path $repo "installer.iss") -Raw
$defaultSpec = Get-Content -LiteralPath (Join-Path $repo "Gemini2API.spec") -Raw
$win11Spec = Get-Content -LiteralPath (Join-Path $repo "Gemini2API-Win11.spec") -Raw
$win11V2Spec = Get-Content -LiteralPath (Join-Path $repo "Gemini2API-Win11-v2.spec") -Raw

$navigationTags = @("home", "server", "cookies", "streaming", "models", "logs", "settings")
foreach ($tag in $navigationTags) {
    if ($mainWindowXaml -notmatch "Tag=`"$tag`"") {
        throw "MainWindow.xaml missing navigation tag: $tag"
    }
    if ($mainWindowCpp -notmatch [regex]::Escape("L`"$tag`"")) {
        throw "MainWindow.xaml.cpp missing navigation handler for tag: $tag"
    }
}

foreach ($shellPattern in @(
    "constexpr double kNavWidth = 48.0;",
    "SystemBackdrop(MicaBackdrop())",
    "ExtendsContentIntoTitleBar(true)",
    "SetTitleBar(m_appTitleBar)",
    "void MainWindow::ToggleLanguage()",
    "void MainWindow::UpdateNavigationState()",
    "m_navItems.push_back(item)",
    "Text(L`"language_button`")",
    "Text(L`"token_metrics`")",
    "Text(L`"operations`")",
    "GEMINI2API_VISUAL_IMAGE",
    "TryConfigurePersonalVisualLayer",
    "Microsoft::UI::Xaml::Media::Imaging::BitmapImage",
    "AutomationProperties::SetAutomationId(languageToggle, L`"LanguageToggleButton`")",
    "AutomationProperties::SetAutomationId(titleText, L`"PageTitle`")",
    "AutomationProperties::SetAutomationId(item, H(L`"Nav`" + navAutomationName + L`"Button`"))",
    "Windows::Data::Json",
    "ParseJsonObject(H(m_cachedStatsJson))",
    "AutomationProperties::SetAutomationId(modeFrame, L`"SegmentedModeBar`")",
    "AutomationProperties::SetAutomationId(listPanel, L`"RecentRequestList`")",
    "AutomationProperties::SetAutomationId(preview, automationId)",
    "L`"RequestBodyPreview`"",
    "L`"ResponseBodyPreview`"",
    "L`"TrendPreviewPanel`"",
    "MakeGeminiIconMark",
    "navColumn.Width(PixelLength(kNavWidth))",
    "item.Width(kNavWidth)",
    "item.Height(kNavWidth)",
    "ScrollViewer contentScroll",
    "HorizontalScrollMode(ScrollMode::Disabled)",
    "void MainWindow::StartLiveRefresh()",
    "m_liveRefreshTimer.Interval(std::chrono::seconds(1))",
    "m_backendRefreshInFlight.exchange(true)",
    "m_backendRefreshInFlight.store(false)",
    "void MainWindow::StartBackendService()",
    "void MainWindow::StopBackendService()",
    "void MainWindow::OpenDashboard()",
    "FindRepositoryRoot()",
    "FindSupervisorExecutable(repoRoot)",
    "gemini2api-supervisor.exe",
    "BackendConfigPath(repoRoot)",
    "m_backendProcess.Start(L`"python`", configPath, 18081, repoRoot, supervisorExe)",
    "m_backendProcess.IsUsingSupervisor()",
    "L`"Rust supervisor PID `"",
    "m_backendProcess.Stop()",
    "ShellExecuteW(nullptr, L`"open`", L`"http://127.0.0.1:18081/dashboard`"",
    "L`"StartBackendButton`"",
    "L`"StopBackendButton`"",
    "L`"OpenDashboardButton`"",
    "L`"ServerCommandRow`"",
    "QueueBackendRefresh",
    "dispatcher.TryEnqueue",
    "NavigateTo(tag, false)"
)) {
    if ($mainWindowCpp -notmatch [regex]::Escape($shellPattern)) {
        throw "MainWindow.xaml.cpp missing native shell pattern: $shellPattern"
    }
}

foreach ($liveRefreshHeaderPattern in @(
    "Microsoft::UI::Dispatching::DispatcherQueueTimer m_liveRefreshTimer",
    "std::atomic_bool m_backendRefreshInFlight",
    "void StartBackendService()",
    "void StopBackendService()",
    "void OpenDashboard()"
)) {
    if ($mainWindowHeader -notmatch [regex]::Escape($liveRefreshHeaderPattern)) {
        throw "MainWindow.xaml.h missing one-second live refresh guard: $liveRefreshHeaderPattern"
    }
}

foreach ($xamlShellPattern in @(
    'CompactPaneLength="48"',
    'OpenPaneLength="48"',
    'IsPaneToggleButtonVisible="False"',
    'IsPaneOpen="False"'
)) {
    if ($mainWindowXaml -notmatch [regex]::Escape($xamlShellPattern)) {
        throw "MainWindow.xaml fallback shell must stay aligned with the 48px native rail: $xamlShellPattern"
    }
}

foreach ($forbiddenNativeUiPattern in @(
    'CompactPaneLength="56"',
    'OpenPaneLength="280"',
    'NavigationView.PaneHeader',
    'LinearGradientBrush',
    'RadialGradientBrush',
    'GradientStop'
)) {
    if ($mainWindowXaml -match [regex]::Escape($forbiddenNativeUiPattern) -or
        $mainWindowCpp -match [regex]::Escape($forbiddenNativeUiPattern)) {
        throw "Native Windows shell must not regress to expanded/decorative UI: $forbiddenNativeUiPattern"
    }
}

foreach ($themePattern in @(
    'AppSurfaceBrush" Color="#202020"',
    'AppHoverBrush" Color="#2D2D2D"',
    'AppSelectedBrush" Color="#3B3B3B"',
    'AppControlBrush" Color="#2B2B2B"',
    'AppBorderBrush" Color="#333333"',
    'AppAccentBrush" Color="#0078D4"',
    'AppDangerBrush" Color="#E81123"',
    'AppSecondaryTextBrush" Color="#999999"',
    'AppDisabledTextBrush" Color="#666666"'
)) {
    $themeFile = Get-Content -LiteralPath (Join-Path $src "Styles\NativeTheme.xaml") -Raw
    if ($themeFile -notmatch [regex]::Escape($themePattern)) {
        throw "NativeTheme.xaml missing Windows 11 dark color token: $themePattern"
    }
}

foreach ($dpiPattern in @(
    "SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)",
    "SetProcessDPIAware()"
)) {
    if ($mainCpp -notmatch [regex]::Escape($dpiPattern)) {
        throw "main.cpp missing high-DPI startup pattern: $dpiPattern"
    }
}

if ($projectFile -notmatch [regex]::Escape('<Manifest Include="src\app.manifest" />')) {
    throw "Gemini2API.WinUI.vcxproj does not embed src\app.manifest"
}
if ($projectFile -notmatch [regex]::Escape('<Content Include="Assets\gemini-icon.png">')) {
    throw "Gemini2API.WinUI.vcxproj does not copy the Gemini icon asset"
}
foreach ($manifestPattern in @(
    "<dpiAwareness",
    "PerMonitorV2",
    "<dpiAware",
    "true/pm",
    "<gdiScaling",
    "false"
)) {
    if ($manifestFile -notmatch [regex]::Escape($manifestPattern)) {
        throw "app.manifest missing high-DPI declaration: $manifestPattern"
    }
}

foreach ($removedSearchPattern in @(
    "SearchBox_QuerySubmitted",
    "AutoSuggestBox",
    "searchSurface",
    "m_searchText",
    "Text(L`"search`")",
    "Search settings",
    "Search models"
)) {
    if ($mainWindowCpp -match [regex]::Escape($removedSearchPattern) -or
        $mainWindowXaml -match [regex]::Escape($removedSearchPattern) -or
        $modelsPageXaml -match [regex]::Escape($removedSearchPattern)) {
        throw "Search UI was removed and must not come back: $removedSearchPattern"
    }
}

foreach ($endpoint in @('L"/"', 'L"/v1/models"', 'L"/admin/stats"')) {
    if ($backendClientCpp -notmatch [regex]::Escape($endpoint)) {
        throw "BackendClient.cpp missing endpoint $endpoint"
    }
}

foreach ($performancePattern in @(
    "constexpr auto kCacheTtl",
    "WinHttpSetTimeouts",
    "kReceiveTimeoutMs",
    "m_adminStatsCache",
    "m_statusCache"
)) {
    if ($backendClientCpp -notmatch [regex]::Escape($performancePattern)) {
        throw "BackendClient.cpp missing native performance guard: $performancePattern"
    }
}

foreach ($winApi in @("WinHttpOpen", "WinHttpConnect", "WinHttpOpenRequest", "WinHttpSendRequest", "WinHttpReceiveResponse", "WinHttpReadData")) {
    if ($backendClientCpp -notmatch $winApi) {
        throw "BackendClient.cpp missing $winApi"
    }
}

foreach ($processApi in @(
    "CreatePipe",
    "SetHandleInformation",
    "CreateProcessW",
    "CREATE_NO_WINDOW",
    "CREATE_SUSPENDED",
    "CreateJobObjectW",
    "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
    "AssignProcessToJobObject",
    "ResumeThread",
    "CreateToolhelp32Snapshot",
    "Process32FirstW",
    "Process32NextW",
    "TerminateProcessTree",
    "TerminateJobObject",
    "TerminateProcess",
    "WaitForSingleObject"
)) {
    if ($backendProcessCpp -notmatch $processApi) {
        throw "BackendProcess.cpp missing $processApi"
    }
}

if ($backendProcessCpp -notmatch "-m gemini_web2api --config") {
    throw "BackendProcess.cpp does not launch python -m gemini_web2api with --config"
}

if ($rootLauncher -notmatch [regex]::Escape("native\scripts\run-winui.ps1")) {
    throw "run-gui.bat must launch the native WinUI shell."
}
if ($rootLauncher -match "python\s+app\.py" -or $rootLauncher -match "python\s+gui_app\.py") {
    throw "run-gui.bat must not launch the legacy Python GUI shell."
}
foreach ($launcherPattern in @(
    "Gemini2API.WinUI.exe",
    "build-winui.ps1",
    "build-supervisor.ps1",
    "gemini2api-supervisor.exe",
    "build.py",
    "Start-Process",
    "Release"
)) {
    if ($nativeLauncher -notmatch [regex]::Escape($launcherPattern)) {
        throw "run-winui.ps1 missing native launcher pattern: $launcherPattern"
    }
}
if ($rootBuildBat -notmatch [regex]::Escape("native\scripts\build-winui.ps1")) {
    throw "build.bat must build the native WinUI shell by default."
}
if ($rootBuildBat -notmatch [regex]::Escape("native\scripts\build-supervisor.ps1")) {
    throw "build.bat must build the Rust supervisor by default."
}
foreach ($forbiddenBuildPattern in @(
    "pip install pyinstaller",
    "pip install PyQt5",
    "python gui_app.py"
)) {
    if ($rootBuildBat -match [regex]::Escape($forbiddenBuildPattern)) {
        throw "build.bat must not default to the legacy Python GUI build: $forbiddenBuildPattern"
    }
}
foreach ($buildPyPattern in @(
    "Gemini2API Native WinUI Build",
    "Gemini2API Rust Supervisor Build",
    "build-winui.ps1",
    "build-supervisor.ps1",
    "gemini2api-supervisor.exe",
    "--legacy-pyqt",
    "build_legacy_pyqt"
)) {
    if ($rootBuildPy -notmatch [regex]::Escape($buildPyPattern)) {
        throw "build.py missing native/legacy build split pattern: $buildPyPattern"
    }
}
foreach ($installerPattern in @(
    '#define MyAppExeName "Gemini2API.WinUI.exe"',
    'Source: "build\native\x64\Release\*"',
    'Excludes: "*.pdb"',
    'SetupIconFile=app_icon.ico'
)) {
    if ($installerScript -notmatch [regex]::Escape($installerPattern)) {
        throw "installer.iss missing native installer pattern: $installerPattern"
    }
}
if ($installerScript -match [regex]::Escape('Source: "dist\Gemini2API\*"') -or
    $installerScript -match [regex]::Escape('#define MyAppExeName "Gemini2API.exe"')) {
    throw "installer.iss must not package the legacy PyInstaller output."
}
foreach ($specText in @($defaultSpec, $win11Spec, $win11V2Spec)) {
    if ($specText -notmatch "raise SystemExit" -or
        $specText -notmatch "native WinUI" -or
        $specText -match "\['gui_app\.py'\]") {
        throw "Legacy PyInstaller spec files must guard against accidental WinUI-named PyQt builds."
    }
}

Write-Host "[OK] Native C++ source consistency checks passed."
