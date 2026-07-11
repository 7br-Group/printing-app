# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Flask web app.
   Build: pyinstaller web_app.spec --clean
"""

import os
import sys

block_cipher = None

a = Analysis(
    ['run_web_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests', 'win32api', 'win32gui',
                   'pythoncom', 'win32con', 'win32com.shell'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PySide6', 'PyQt5', 'PyQt6',
              'PySide2', 'matplotlib', 'scipy', 'PIL',
              'numpy', 'pandas', 'cv2'],
    noarchive=False,
    optimize=1,
)

# Add the entire web_app folder (templates, static, app.py)
a.datas += Tree('web_app', prefix='web_app')

# Add the database module
a.datas += Tree('database', prefix='database')

# Add the WhatsApp Node.js server (node.exe, server.js, node_modules)
a.datas += Tree('whatsapp_server', prefix='whatsapp_server')

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WebApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
