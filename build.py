"""Build Gemini2API desktop artifacts.

Default build target is the native C++/WinUI shell. The old PyQt package is
kept behind --legacy-pyqt so existing fallback workflows still exist without
being the normal Windows app path.
"""
import argparse
import os
import shutil
import subprocess
import sys


DIST_DIR = "dist"
APP_NAME = "Gemini2API"


def _run(cmd):
    return subprocess.run(cmd, check=False).returncode == 0


def build_supervisor(configuration="Release", platform="x64"):
    print("=" * 50)
    print("  Gemini2API Rust Supervisor Build")
    print("=" * 50)
    print()

    script = os.path.join("native", "scripts", "build-supervisor.ps1")
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script,
        "-RequireToolchain",
    ]
    if configuration == "Release":
        cmd.append("-Release")

    if not _run(cmd):
        print("\n[FAIL] Rust supervisor build failed.")
        return False

    profile = "release" if configuration == "Release" else "debug"
    supervisor_path = os.path.join(
        "native",
        "supervisor-rs",
        "target",
        profile,
        "gemini2api-supervisor.exe",
    )
    if not os.path.exists(supervisor_path):
        print(f"\n[FAIL] Rust supervisor EXE not found: {supervisor_path}")
        return False

    output_dir = os.path.join("build", "native", platform, configuration)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "gemini2api-supervisor.exe")
    shutil.copy2(supervisor_path, output_path)
    print(f"[OK] Rust supervisor copied: {output_path}")
    return True


def build_native(configuration="Release", platform="x64"):
    print("=" * 50)
    print("  Gemini2API Native WinUI Build")
    print("=" * 50)
    print()
    script = os.path.join("native", "scripts", "build-winui.ps1")
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script,
        "-Configuration",
        configuration,
        "-Platform",
        platform,
    ]
    if not _run(cmd):
        print("\n[FAIL] Native WinUI build failed.")
        return False

    if not build_supervisor(configuration=configuration, platform=platform):
        return False

    exe_path = os.path.join("build", "native", platform, configuration, "Gemini2API.WinUI.exe")
    if not os.path.exists(exe_path):
        print(f"\n[FAIL] Native EXE not found: {exe_path}")
        return False

    print()
    print("=" * 50)
    print("  BUILD SUCCESS")
    print(f"  Native EXE: {exe_path}")
    print("  Run: run-gui.bat")
    print("=" * 50)
    return True


def clean_legacy():
    for directory in [DIST_DIR, os.path.join("build", "legacy-pyqt")]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
    if os.path.exists(f"{APP_NAME}.spec"):
        os.remove(f"{APP_NAME}.spec")
    print("[OK] Cleaned legacy PyQt build directories")


def build_legacy_pyqt():
    print("=" * 50)
    print("  Gemini2API Legacy PyQt Build")
    print("=" * 50)
    print()
    print("  This is a fallback package. The normal Windows app is C++/WinUI.")
    print()

    try:
        import PyInstaller  # noqa: F401
        print("[OK] PyInstaller installed")
    except ImportError:
        print("[...] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    try:
        import PyQt5  # noqa: F401
        print("[OK] PyQt5 installed")
    except ImportError:
        print("[...] Installing PyQt5...")
        subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"], check=True)

    clean_legacy()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        f"{APP_NAME}-LegacyPyQt",
        "--windowed",
        "--onedir",
        "--clean",
        "--noconfirm",
        "--add-data",
        "gemini_web2api;gemini_web2api",
        "--add-data",
        "gui;gui",
        "--add-data",
        "extension;extension",
        "--add-data",
        "config.example.json;.",
        "--add-data",
        "logo.png;.",
        "--hidden-import",
        "httpx",
        "--hidden-import",
        "tiktoken",
        "--hidden-import",
        "PyQt5",
        "--hidden-import",
        "PyQt5.QtWidgets",
        "--hidden-import",
        "PyQt5.QtCore",
        "--hidden-import",
        "PyQt5.QtGui",
        "--hidden-import",
        "pystray",
        "--hidden-import",
        "PIL",
        "gui_app.py",
    ]

    if not _run(cmd):
        print("\n[FAIL] Legacy PyQt build failed.")
        return False

    app_dir = os.path.join(DIST_DIR, f"{APP_NAME}-LegacyPyQt")
    exe_path = os.path.join(app_dir, f"{APP_NAME}-LegacyPyQt.exe")
    if not os.path.exists(exe_path):
        print(f"\n[FAIL] Legacy EXE not found: {exe_path}")
        return False

    shutil.copy("config.example.json", app_dir)
    if os.path.exists("gemini_web2api_standalone.py"):
        shutil.copy("gemini_web2api_standalone.py", app_dir)

    print()
    print("=" * 50)
    print("  LEGACY BUILD SUCCESS")
    print(f"  Output: {app_dir}")
    print("=" * 50)
    return True


def main():
    parser = argparse.ArgumentParser(description="Build Gemini2API desktop artifacts.")
    parser.add_argument("--legacy-pyqt", action="store_true", help="Build the old PyQt fallback package.")
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Release")
    parser.add_argument("--platform", choices=["x64"], default="x64")
    args = parser.parse_args()

    if args.legacy_pyqt:
        success = build_legacy_pyqt()
    else:
        success = build_native(configuration=args.configuration, platform=args.platform)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
