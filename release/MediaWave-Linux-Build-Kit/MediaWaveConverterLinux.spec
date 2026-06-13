# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for MediaWave Converter — Linux one-folder build.
# Build on a Linux machine:
#   python -m PyInstaller --noconfirm MediaWaveConverterLinux.spec

import os
import sys

_base = os.path.dirname(os.path.abspath(SPEC))

def _dir_if_exists(src, dst):
    return [(src, dst)] if os.path.isdir(os.path.join(_base, src)) else []

def _file_if_exists(src, dst):
    return [(src, dst)] if os.path.isfile(os.path.join(_base, src)) else []

datas = (
    _dir_if_exists("logos", "logos")
    + _dir_if_exists("Fonts", "Fonts")
    + _dir_if_exists("bin", "bin")
    + _dir_if_exists("docs", "docs")
)

_icon_png = os.path.join(_base, "icons", "mediawave_converter.png")
_icon_file = _icon_png if os.path.exists(_icon_png) else None

a = Analysis(
    ["mediawave_converter.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "xml",
        "pydoc",
        "doctest",
        "ftplib",
        "getpass",
        "getopt",
        "imaplib",
        "smtplib",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MediaWaveConverter",
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
    icon=_icon_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MediaWaveConverter",
)
