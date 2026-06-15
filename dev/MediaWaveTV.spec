# -*- mode: python ; coding: utf-8 -*-

import os

_spec_dir = os.path.dirname(os.path.abspath(SPEC))
_base = os.path.dirname(_spec_dir)


a = Analysis(
    [os.path.join(_base, 'channelsurfer2000.py')],
    pathex=[_base],
    binaries=[],
    datas=[
        (os.path.join(_base, 'assets'), 'assets'),
        (os.path.join(_base, 'logos'), 'logos'),
        (os.path.join(_base, 'Fonts'), 'Fonts'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MediaWaveTV',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MediaWaveTV',
)
app = BUNDLE(
    coll,
    name='MediaWaveTV.app',
    icon=None,
    bundle_identifier=None,
)
