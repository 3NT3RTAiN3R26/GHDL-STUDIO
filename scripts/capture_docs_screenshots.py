#!/usr/bin/env python3
"""Capture GHDL Studio UI screenshots for the documentation site."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ghdl_studio.main_window import MainWindow  # noqa: E402
from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM  # noqa: E402
from ghdl_studio.settings import AppSettings  # noqa: E402
from ghdl_studio.theme import apply_dark_theme  # noqa: E402
from ghdl_studio.widgets.run_settings_dialog import RunSettingsDialog  # noqa: E402
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog  # noqa: E402

OUT = ROOT / "docs" / "images"
COUNTER = ROOT / "examples" / "counter"
ADDER = ROOT / "examples" / "adder"


def _grab(widget, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    pixmap = widget.grab()
    if not pixmap.save(str(path), "PNG"):
        raise SystemExit(f"Failed to save {path}")
    print(f"wrote {path} ({pixmap.width()}x{pixmap.height()})")


def _pump(app: QApplication, ms: int = 80) -> None:
    deadline = Qt.TimerType.PreciseTimer
    loop = True

    def stop() -> None:
        nonlocal loop
        loop = False

    QTimer.singleShot(ms, stop)
    while loop:
        app.processEvents()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GHDL Studio")
    apply_dark_theme(app)

    settings = AppSettings()

    # --- Startup dialog ---
    startup = StartupModeDialog(settings)
    startup.setWindowTitle("GHDL Studio — Choose mode")
    startup.show()
    _pump(app, 120)
    _grab(startup, "docs_startup_mode.png")
    startup.close()

    # --- Normal mode with counter sources + editor ---
    normal = MainWindow(mode=MODE_NORMAL)
    normal.resize(1280, 800)
    normal.show()
    _pump(app, 150)
    files = [
        str(COUNTER / "counter.vhd"),
        str(COUNTER / "counter_tb.vhd"),
    ]
    normal._file_explorer.add_files(files)
    normal._open_file_in_editor(files[0])
    if hasattr(normal, "_top_unit_combo"):
        normal._top_unit_combo.setCurrentText("counter_tb")
    if hasattr(normal, "_stop_time_edit"):
        normal._stop_time_edit.setText("200ns")
    normal._log_console.append_command("ghdl -a --std=08 counter.vhd")
    normal._log_console.append_success("[Analyze] finished successfully (exit code 0).")
    _pump(app, 200)
    _grab(normal, "docs_normal_mode.png")

    # Settings dialog (from normal window)
    dlg = RunSettingsDialog(settings, normal._run_options, normal)
    dlg.setWindowTitle("GHDL Studio — Settings")
    dlg.show()
    _pump(app, 150)
    _grab(dlg, "docs_settings.png")
    dlg.reject()
    dlg.close()
    normal.close()

    # --- OSVVM mode with multiple .pro files ---
    pro_main = ADDER / "adder.pro"
    pro_alt = Path("/tmp/ghdl_studio_docs_alt.pro")
    pro_alt.write_text(
        "# Alternate OSVVM entry (docs screenshot only)\n"
        "SetVHDLVersion 2008\n",
        encoding="utf-8",
    )
    settings.pro_files = [str(pro_main.resolve()), str(pro_alt.resolve())]
    settings.last_pro_file = str(pro_main.resolve())

    osvvm = MainWindow(mode=MODE_OSVVM, pro_path=str(pro_main))
    osvvm.resize(1280, 800)
    osvvm.show()
    _pump(app, 200)
    osvvm._file_explorer.clear_files()
    osvvm._file_explorer.add_files([str(pro_main), str(pro_alt)])
    osvvm._file_explorer.set_active_file(str(pro_main.resolve()))
    osvvm._open_file_in_editor(str(pro_main))
    osvvm._log_console.append_output(
        "%%   13 ns    DONE    PASSED    adder_tb  Passed: 13  Affirmations Checked: 13"
    )
    osvvm._log_console.append_success("[OSVVM Build] finished successfully (exit code 0).")
    _pump(app, 250)
    _grab(osvvm, "docs_osvvm_mode.png")
    osvvm.close()

    QTimer.singleShot(50, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
