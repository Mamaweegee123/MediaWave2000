# -*- mode: python ; coding: utf-8 -*-


logo_files = []
if __import__("os").path.exists("logos"):
    logo_files.append(("logos", "logos"))

font_files = []
if __import__("os").path.exists("Fonts"):
    font_files.append(("Fonts", "Fonts"))

binary_files = []
if __import__("os").path.exists("bin"):
    binary_files.append(("bin", "bin"))


a = Analysis(
    ["mediawave_converter.py"],
    pathex=[],
    binaries=[],
    datas=logo_files + font_files + binary_files,
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
app = BUNDLE(
    coll,
    name="MediaWaveConverter.app",
    icon=None,
    bundle_identifier=None,
)
