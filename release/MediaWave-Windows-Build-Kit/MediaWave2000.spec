# -*- mode: python ; coding: utf-8 -*-

import os
import sys

_base = os.path.dirname(os.path.abspath(SPEC))

def _dir_if_exists(src, dst):
    return [(src, dst)] if os.path.isdir(os.path.join(_base, src)) else []

datas = (
    _dir_if_exists("assets", "assets")
    + _dir_if_exists("logos", "logos")
    + _dir_if_exists("ds_digital", "ds_digital")
    + _dir_if_exists("Fonts", "Fonts")
    + _dir_if_exists("docs", "docs")
)

_icon_icns = os.path.join(_base, "icons", "mediawave2000.icns")
_icon_ico  = os.path.join(_base, "icons", "mediawave2000.ico")
_icon_file = (
    _icon_icns if os.path.exists(_icon_icns) and sys.platform == "darwin"
    else _icon_ico  if os.path.exists(_icon_ico)
    else None
)

a = Analysis(
    ["channelsurfer2000.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["hooks/pyi_rth_qtwebengine.py"],
    excludes=[
        "tkinter",
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
    name="MediaWave2000",
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
    name="MediaWave2000",
)
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="MediaWave2000.app",
        icon=_icon_icns if os.path.exists(_icon_icns) else None,
        bundle_identifier="com.mamaweegee.mediawave2000",
    )
