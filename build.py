"""Build script for Gemini2API Desktop - customtkinter version."""
import os
import sys
import shutil
import subprocess

DIST_DIR = "dist"
BUILD_DIR = "build"
APP_NAME = "Gemini2API"


def clean():
    """清理构建目录"""
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
    if os.path.exists(f"{APP_NAME}.spec"):
        os.remove(f"{APP_NAME}.spec")
    print("[OK] Cleaned build directories")


def build():
    """构建EXE"""
    print("=" * 50)
    print("  Gemini2API Desktop Build")
    print("=" * 50)
    print()

    # 检查依赖
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("[...] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    try:
        import customtkinter
        print("[OK] customtkinter installed")
    except ImportError:
        print("[...] Installing customtkinter...")
        subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter"], check=True)

    # 清理
    clean()

    print()
    print("[...] Building EXE...")
    print()

    # 使用PyInstaller构建
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",
        "--onedir",
        "--clean",
        "--noconfirm",
        "--add-data", "gemini_web2api;gemini_web2api",
        "--add-data", "extension;extension",
        "--add-data", "config.example.json;.",
        "--add-data", "logo.png;.",
        "--hidden-import", "httpx",
        "--hidden-import", "tiktoken",
        "--hidden-import", "customtkinter",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "darkdetect",
        "--exclude-module", "PyQt5",
        "app.py"
    ]

    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        print(f"\n[FAIL] Build failed with exit code {ret.returncode}")
        return False

    # 检查输出
    app_dir = os.path.join(DIST_DIR, APP_NAME)
    exe_path = os.path.join(app_dir, f"{APP_NAME}.exe")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, dirnames, filenames in os.walk(app_dir)
            for filename in filenames
        ) / (1024 * 1024)
        
        print()
        print("=" * 50)
        print(f"  BUILD SUCCESS!")
        print(f"  Output: {app_dir}")
        print(f"  EXE: {exe_path}")
        print(f"  EXE Size: {size_mb:.1f} MB")
        print(f"  Total Size: {total_size:.1f} MB")
        print("=" * 50)
        
        return True
    else:
        print(f"\n[FAIL] EXE not found at {exe_path}")
        return False


if __name__ == "__main__":
    success = build()
    if success:
        print("\nTo run the app:")
        print(f"  {DIST_DIR}\\{APP_NAME}\\{APP_NAME}.exe")
    sys.exit(0 if success else 1)
