# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# Exclude heavy unnecessary scientific & server packages
excludes = [
    'torch', 'torchvision', 'cv2', 'opencv', 'scipy', 'matplotlib',
    'polars', 'polars_runtime_32', 'openpyxl',
    'et_xmlfile', 'fastapi', 'starlette', 'uvicorn',
    'playwright', 'pyarrow', 'lxml', 'docx', 'pypdf', 'tkinter',
    'unittest', 'test', 'tests'
]

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('app/assets', 'app/assets'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        'PyQt6.QtSvg',
        'spotipy',
        'requests',
        'urllib.request',
        'redis',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='spfnotch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/assets/icon.ico',
)
