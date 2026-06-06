# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Gemini2API Desktop - PyQt5 version."""

block_cipher = None

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gui', 'gui'),
        ('gemini_web2api', 'gemini_web2api'),
        ('extension', 'extension'),
        ('config.example.json', '.'),
    ],
    hiddenimports=[
        'httpx',
        'tiktoken',
        'browser_cookie3',
        'websocket',
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        '_cffi_backend',
        'cffi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'customtkinter',
        'darkdetect',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Gemini2API',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Gemini2API',
)
