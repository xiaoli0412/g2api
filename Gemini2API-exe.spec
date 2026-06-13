# -*- mode: python ; coding: utf-8 -*-
"""
Gemini2API PyInstaller spec - builds a distributable Windows EXE.
Usage: pyinstaller Gemini2API-exe.spec --clean --noconfirm
"""
import os
import importlib

block_cipher = None
ROOT = SPECPATH

# ── Locate customtkinter data files ─────────────────────────────
ctk_dir = os.path.dirname(importlib.import_module("customtkinter").__file__)

# ── Data files to bundle (non-Python assets only) ───────────────
datas = [
    (ctk_dir, "customtkinter"),
    (os.path.join(ROOT, "config.example.json"), "."),
    (os.path.join(ROOT, "logo.png"), "."),
    (os.path.join(ROOT, "extension"), "extension"),
    (os.path.join(ROOT, "gemini_web2api", "dashboard.html"), "gemini_web2api"),
]

ico_path = os.path.join(ROOT, "app_icon.ico")
if os.path.exists(ico_path):
    datas.append((ico_path, "."))

# ── Hidden imports (only third-party + deep submodules) ─────────
hiddenimports = [
    "gemini_web2api",
    "gemini_web2api.__main__",
    "gemini_web2api.config",
    "gemini_web2api.server",
    "gemini_web2api.gemini",
    "gemini_web2api.models",
    "gemini_web2api.multimodal",
    "gemini_web2api.tools",
    "gemini_web2api.cookies",
    "gemini_web2api.cookie_manager",
    "gemini_web2api.admin",
    "gemini_web2api.sse",
    "gemini_web2api.capabilities",
    "gemini_web2api.stats",
    "gemini_web2api.proxy_builtin",
    "gemini_web2api.adapters",
    "gemini_web2api.artifact_store",
    "gemini_web2api.tokenizer",
    "httpx",
    "httpx._transports.default",
    "tiktoken",
    "tiktoken_ext.openai_public",
    "pystray",
    "pystray._win32",
    "darkdetect",
]

try:
    import browser_cookie3
    hiddenimports.append("browser_cookie3")
except ImportError:
    pass

# ── Analysis ─────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib", "numpy", "scipy", "pandas",
        "unittest", "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ── Bundle ───────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gemini2API",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=ico_path if os.path.exists(ico_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Gemini2API",
)
