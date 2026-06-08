# -*- mode: python ; coding: utf-8 -*-
"""
UltraWater Client — PyInstaller Spec
Run: pyinstaller UltraWater.spec

This builds a standalone executable with:
  - Python runtime bundled (no Python install needed)
  - customtkinter themes and assets included
  - All dependencies included
  - Wizard and main launcher as single package
"""

import os
import sys
import platform
from pathlib import Path

# ── Paths ──────────────────────────────────────────────
ROOT = Path(SPECPATH)
SRC  = ROOT  # source files are in root

# Find customtkinter
try:
    import customtkinter
    CTK_PATH = Path(customtkinter.__file__).parent
except ImportError:
    raise SystemExit("customtkinter not found! pip install customtkinter")

# ── Analysis ───────────────────────────────────────────

a = Analysis(
    [str(SRC / 'ultrawater.py')],   # main entry
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        # Bundle customtkinter (themes, images, fonts)
        (str(CTK_PATH), 'customtkinter/'),
        # Bundle wizard alongside main
        (str(SRC / 'wizard.py'), '.'),
    ],
    hiddenimports=[
        'customtkinter',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'minecraft_launcher_lib',
        'minecraft_launcher_lib.install',
        'minecraft_launcher_lib.command',
        'minecraft_launcher_lib.fabric',
        'minecraft_launcher_lib.utils',
        'requests',
        'urllib.request',
        'ssl',
        'json',
        'threading',
        'subprocess',
        'shutil',
        'platform',
        'pathlib',
        'dataclasses',
        'enum',
        'queue',
        'hashlib',
        'zipfile',
        'tarfile',
        'uuid',
        'webbrowser',
        'logging',
        're',
        'traceback',
        'PIL',
        'PIL.Image',
        'pkg_resources',
        'packaging',
        'charset_normalizer',
        'certifi',
        'idna',
        'wizard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'test',
        'unittest',
        'doctest',
        'pdb',
        'pydoc',
        'xmlrpc',
        'lib2to3',
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

# ── Platform-specific exe settings ────────────────────

IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS   = platform.system() == 'Darwin'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UltraWater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,             # UPX can cause AV false positives — skip it
    console=False,         # Windowed (no console) on Windows/Mac
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment and add your icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='UltraWater',
)

# macOS .app bundle
if IS_MACOS:
    app = BUNDLE(
        coll,
        name='UltraWater.app',
        icon='assets/icon.icns',
        bundle_identifier='gg.ultrawater.client',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '2.0.0',
            'CFBundleVersion': '2.0.0',
            'CFBundleName': 'UltraWater Client',
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
        },
    )
