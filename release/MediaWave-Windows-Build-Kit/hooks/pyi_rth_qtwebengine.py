# PyInstaller runtime hook — fix QtWebEngine paths and GPU context in macOS .app bundles.
#
# Must run before any Qt/PySide6 imports so the env vars and application
# attributes are in place before QApplication is constructed.

import os
import sys

if sys.platform == "darwin" and getattr(sys, "frozen", False):
    # sys.executable → .../Contents/MacOS/<exe>
    _macos_dir    = os.path.dirname(sys.executable)   # .../Contents/MacOS
    _contents_dir = os.path.dirname(_macos_dir)        # .../Contents

    # ── Framework paths ───────────────────────────────────────────────────────
    _fw_pyside = os.path.join(_contents_dir, "Frameworks", "PySide6", "Qt", "lib",
                              "QtWebEngineCore.framework")

    # 1. Helper process (QtWebEngineProcess.app)
    _helper = os.path.join(_fw_pyside, "Helpers",
                           "QtWebEngineProcess.app", "Contents", "MacOS",
                           "QtWebEngineProcess")
    if os.path.exists(_helper):
        os.environ.setdefault("QTWEBENGINEPROCESS_PATH", _helper)

    # 2. Resource pak files (qtwebengine_resources.pak, icudtl.dat, locales…)
    _resources = os.path.join(_fw_pyside, "Resources")
    if os.path.isdir(_resources):
        os.environ.setdefault("QTWEBENGINE_RESOURCES_PATH", _resources)

    # 3. Chromium locale files (subfolder of resources)
    _locales = os.path.join(_resources, "qtwebengine_locales")
    if os.path.isdir(_locales):
        os.environ.setdefault("QTWEBENGINE_LOCALES_PATH", _locales)

    # ── Sandbox / rendering fixes ─────────────────────────────────────────────
    # Disable Chromium's GPU sandbox so the GPU helper can access Metal/OpenGL
    # resources inside the frozen .app bundle.  Without this the GPU process
    # starts but silently fails to composite, leaving QWebEngineView black.
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    # Chromium flags:
    #   --disable-gpu          – CRITICAL: forces Chromium software (Skia-CPU)
    #                            rendering.  On macOS 15+ inside a PyInstaller
    #                            bundle the Metal compositor is sandboxed and
    #                            silently produces nothing, so the only reliable
    #                            fix is to bypass the GPU path entirely.
    #   --disable-gpu-sandbox  – belt-and-suspenders for GPU helper process.
    #   --no-sandbox           – belt-and-suspenders for renderer process.
    _chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    _extra = []
    for _flag in ("--disable-gpu", "--disable-gpu-sandbox", "--no-sandbox"):
        if _flag not in _chromium_flags:
            _extra.append(_flag)
    if _extra:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
            (_chromium_flags + " " + " ".join(_extra)).strip()
        )

# 4. AA_ShareOpenGLContexts must be set before QApplication is created.
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
except Exception:
    pass
