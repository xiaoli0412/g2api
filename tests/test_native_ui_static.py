"""Static guards for the native WinUI shell design contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE_SRC = ROOT / "native" / "Gemini2API.WinUI" / "src"


def _read(relative: str) -> str:
    return (NATIVE_SRC / relative).read_text(encoding="utf-8")


def test_native_shell_uses_48px_icon_rail_even_in_xaml_fallback():
    cpp = _read("MainWindow.xaml.cpp")
    xaml = _read("MainWindow.xaml")

    assert "constexpr double kNavWidth = 48.0;" in cpp
    assert "navColumn.Width(PixelLength(kNavWidth))" in cpp
    assert "item.Width(kNavWidth)" in cpp
    assert "item.Height(kNavWidth)" in cpp
    assert 'CompactPaneLength="48"' in xaml
    assert 'OpenPaneLength="48"' in xaml
    assert 'IsPaneToggleButtonVisible="False"' in xaml
    assert 'NavigationView.PaneHeader' not in xaml
    assert 'CompactPaneLength="56"' not in xaml
    assert 'OpenPaneLength="280"' not in xaml


def test_native_theme_keeps_windows_11_dark_tokens_without_gradients():
    theme = _read("Styles/NativeTheme.xaml")
    cpp = _read("MainWindow.xaml.cpp")
    xaml = _read("MainWindow.xaml")

    for token in (
        'AppSurfaceBrush" Color="#202020"',
        'AppHoverBrush" Color="#2D2D2D"',
        'AppSelectedBrush" Color="#3B3B3B"',
        'AppControlBrush" Color="#2B2B2B"',
        'AppBorderBrush" Color="#333333"',
        'AppAccentBrush" Color="#0078D4"',
        'AppDangerBrush" Color="#E81123"',
        'AppSecondaryTextBrush" Color="#999999"',
        'AppDisabledTextBrush" Color="#666666"',
    ):
        assert token in theme

    native_ui_text = "\n".join([theme, cpp, xaml])
    for forbidden in ("LinearGradientBrush", "RadialGradientBrush", "GradientStop"):
        assert forbidden not in native_ui_text


def test_native_shell_keeps_mica_dpi_language_and_body_viewers():
    cpp = _read("MainWindow.xaml.cpp")
    main_cpp = _read("main.cpp")

    for token in (
        "SystemBackdrop(MicaBackdrop())",
        "DesktopAcrylicBackdrop()",
        "ExtendsContentIntoTitleBar(true)",
        "SetTitleBar(m_appTitleBar)",
        "ToggleLanguage()",
        'L"RequestBodyPreview"',
        'L"ResponseBodyPreview"',
        'L"TrendPreviewPanel"',
        'L"NativeQuotaTable"',
        'L"NativeQuotaSummary"',
        'L"NativeQuotaShareBar"',
        'L"NativeModelUsageTable"',
        'L"NativeModelUsageSummary"',
        'L"NativeModelShareBar"',
        'AutomationProperties::SetAutomationId(item, H(L"Nav" + navAutomationName + L"Button"))',
        "MakeGeminiIconMark",
    ):
        assert token in cpp

    assert "DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2" in main_cpp


def test_native_models_page_uses_new_api_style_native_tables_not_json_dump():
    cpp = _read("MainWindow.xaml.cpp")

    for token in (
        "void AppendModelUsageTable",
        "MakeModelUsageGridRow",
        "MakeQuotaGridRow",
        "AppendNativeSummaryStrip",
        "AppendShareBarCell",
        "ProgressBar bar",
        "AppendModelUsageTable(m_contentPanel, stats, m_useChinese);",
    ):
        assert token in cpp

    assert "Model stats JSON" not in cpp
    assert "模型统计 JSON" not in cpp


def test_native_shell_has_low_cost_one_second_live_refresh():
    cpp = _read("MainWindow.xaml.cpp")
    header = _read("MainWindow.xaml.h")

    assert "DispatcherQueueTimer m_liveRefreshTimer" in header
    assert "std::atomic_bool m_backendRefreshInFlight" in header
    assert "StartLiveRefresh();" in cpp
    assert "m_liveRefreshTimer.Interval(std::chrono::seconds(1));" in cpp
    assert "m_backendRefreshInFlight.exchange(true)" in cpp
    assert "m_backendRefreshInFlight.store(false)" in cpp


def test_native_server_page_exposes_real_backend_process_controls():
    cpp = _read("MainWindow.xaml.cpp")
    header = _read("MainWindow.xaml.h")

    for token in (
        "void StartBackendService();",
        "void StopBackendService();",
        "void OpenDashboard();",
    ):
        assert token in header

    for token in (
        "void MainWindow::StartBackendService()",
        "void MainWindow::StopBackendService()",
        "void MainWindow::OpenDashboard()",
        "FindRepositoryRoot()",
        "FindSupervisorExecutable(repoRoot)",
        "gemini2api-supervisor.exe",
        "BackendConfigPath(repoRoot)",
        'm_backendProcess.Start(L"python", configPath, 18081, repoRoot, supervisorExe)',
        "m_backendProcess.IsUsingSupervisor()",
        "m_backendProcess.Stop()",
        'ShellExecuteW(nullptr, L"open", L"http://127.0.0.1:18081/dashboard"',
        'L"StartBackendButton"',
        'L"StopBackendButton"',
        'L"OpenDashboardButton"',
        'L"ServerCommandRow"',
        'm_backendProcess.ProcessId()',
        'L"Rust supervisor PID "',
    ):
        assert token in cpp

    backend_process = _read("BackendProcess.cpp")
    for token in (
        '<< L" run "',
        "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
        "CreateJobObjectW",
        "AssignProcessToJobObject",
        "CreateToolhelp32Snapshot",
        "Process32FirstW",
        "Process32NextW",
        "TerminateProcessTree",
        "TerminateJobObject",
        "CREATE_NO_WINDOW | CREATE_SUSPENDED",
        "ResumeThread",
    ):
        assert token in backend_process

    supervisor = (ROOT / "native" / "supervisor-rs" / "src" / "main.rs").read_text(encoding="utf-8")
    for token in (
        "ManagedChild",
        "CreateJobObjectW",
        "SetInformationJobObject",
        "AssignProcessToJobObject",
        "TerminateJobObject",
        "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
        "CREATE_NO_WINDOW",
        "child.terminate()",
    ):
        assert token in supervisor

    runtime_verifier = (ROOT / "native" / "scripts" / "verify-winui-runtime.ps1").read_text(encoding="utf-8")
    all_verifier = (ROOT / "native" / "scripts" / "verify-all-native.ps1").read_text(encoding="utf-8")
    assert "[switch]$ExerciseBackendControls" in runtime_verifier
    assert "[switch]$ExerciseBackendControls" in all_verifier
    assert "Invoke-AutomationElementCenterById" in runtime_verifier
    assert '"NavServerButton"' in runtime_verifier
    assert '"NavStreamingButton"' in runtime_verifier
    assert "Wait-LocalBackendState -Reachable $true" in runtime_verifier
    assert "Wait-LocalBackendState -Reachable $false" in runtime_verifier
