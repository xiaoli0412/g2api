"""Build script for Gemini2API Desktop - PyQt5 Windows 11 Style App."""
import os
import sys
import shutil
import subprocess

DIST_DIR = "dist"
BUILD_DIR = "build"
APP_NAME = "Gemini2API"


def build():
    print("=" * 50)
    print("  Gemini2API Desktop Build")
    print("=" * 50)
    print()

    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("[...] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        import PyInstaller

    try:
        import PyQt5
        print(f"[OK] PyQt5")
    except ImportError:
        print("[...] Installing PyQt5...")
        subprocess.run([sys.executable, "-m", "pip", "install", "PyQt5"], check=True)

    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)

    print()
    print("[...] Building EXE with PyInstaller...")
    print()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",
        "--onedir",
        "--clean",
        "--log-level", "WARN",
        "--add-data", "gui;gui",
        "--add-data", "gemini_web2api;gemini_web2api",
        "--add-data", "extension;extension",
        "--hidden-import", "PyQt5",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "gui_app.py"
    ]

    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        print(f"\n[FAIL] Build failed with exit code {ret.returncode}")
        return False

    app_dir = os.path.join(DIST_DIR, APP_NAME)
    exe_path = os.path.join(app_dir, f"{APP_NAME}.exe")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  BUILD SUCCESS")
        print(f"  Output: {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
        print("=" * 50)
    else:
        print(f"\n[FAIL] EXE not found at {exe_path}")
        return False

    print()
    print("To create installer, install Inno Setup and run:")
    print(f"  iscc installer.iss")
    print()
    return True


if __name__ == "__main__":
    build()
