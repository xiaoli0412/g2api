"""Static guards for native Windows entry points."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_root_gui_launcher_uses_native_winui_shell():
    launcher = _read("run-gui.bat")
    native_launcher = _read("native/scripts/run-winui.ps1")
    assert "native\\scripts\\run-winui.ps1" in launcher
    assert "gemini2api-supervisor.exe" in native_launcher
    assert "build.py" in native_launcher
    assert "build-supervisor.ps1" in native_launcher
    assert "python app.py" not in launcher
    assert "python gui_app.py" not in launcher


def test_default_build_targets_native_winui():
    build_bat = _read("build.bat")
    build_py = _read("build.py")
    assert "native\\scripts\\build-winui.ps1" in build_bat
    assert "native\\scripts\\build-supervisor.ps1" in build_bat
    assert "build.py" in build_bat
    assert "Gemini2API Native WinUI Build" in build_py
    assert "Gemini2API Rust Supervisor Build" in build_py
    assert "build-supervisor.ps1" in build_py
    assert "gemini2api-supervisor.exe" in build_py
    assert "--legacy-pyqt" in build_py
    assert "python gui_app.py" not in build_bat
    assert "pip install pyinstaller" not in build_bat.lower()


def test_installer_packages_native_release_output():
    installer = _read("installer.iss")
    assert '#define MyAppExeName "Gemini2API.WinUI.exe"' in installer
    assert 'Source: "build\\native\\x64\\Release\\*"' in installer
    assert 'Excludes: "*.pdb"' in installer
    assert "SetupIconFile=app_icon.ico" in installer
    assert 'Source: "dist\\Gemini2API\\*"' not in installer
    assert '#define MyAppExeName "Gemini2API.exe"' not in installer


def test_pyinstaller_specs_are_not_winui_entrypoints():
    for name in ("Gemini2API.spec", "Gemini2API-Win11.spec", "Gemini2API-Win11-v2.spec"):
        text = _read(name)
        assert "raise SystemExit" in text
        assert "native WinUI" in text
        assert "['gui_app.py']" not in text


def test_legacy_python_ui_does_not_advertise_old_pyinstaller_exe():
    for name in ("app.py", "gui/pages/settings_page.py", "PROJECT_SUMMARY.md", "FEATURES.md"):
        text = _read(name)
        assert "dist\\Gemini2API\\Gemini2API.exe" not in text
        normalized = text.replace("\\\\", "/").replace("\\", "/")
        assert "build/native/x64/Release/Gemini2API.WinUI.exe" in normalized


def test_public_docs_do_not_promote_python_gui_as_main_entrypoint():
    for name in (
        "README.md",
        "README_CN.md",
        "START_HERE.md",
        "START_HERE_CN.md",
        "PROJECT_SUMMARY.md",
        "FEATURES.md",
        "test_comprehensive.py",
    ):
        text = _read(name)
        assert "python gui_app.py" not in text
    assert "run-gui.bat" in _read("START_HERE.md")
    assert "run-gui.bat" in _read("START_HERE_CN.md")
