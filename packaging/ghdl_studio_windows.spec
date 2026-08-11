# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows portable GHDL Studio build.

Build (on Windows)::

    powershell -File scripts/build_windows_portable.ps1

Produces ``dist/GHDL-Studio/GHDL-Studio.exe`` (onedir) plus bundled examples.
"""

from __future__ import annotations

from pathlib import Path

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPECDIR = Path(SPEC).resolve().parent  # noqa: F821 — PyInstaller injects SPEC
ROOT = SPECDIR.parent
ENTRY = SPECDIR / "windows_entry.py"

# Package data (e.g. resources/combo_down_arrow.png).
datas = collect_data_files("ghdl_studio")

# Prefer a lean portable zip: OSVVM HTML falls back to QTextBrowser when
# QtWebEngine is absent (see widgets/html_report_view.py).
excludes = [
    "PySide6.QtWebEngine",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtLocation",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "tkinter",
    "matplotlib",
    "numpy",
    "Xlib",
]

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    *collect_submodules("ghdl_studio"),
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GHDL-Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "src" / "ghdl_studio" / "resources" / "logo_icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GHDL-Studio",
)
