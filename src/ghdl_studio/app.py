"""Einstiegspunkt der Anwendung."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from ghdl_studio.main_window import MainWindow
from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM
from ghdl_studio.settings import AppSettings
from ghdl_studio.surfer_embed import ensure_linux_xcb_platform
from ghdl_studio.theme import apply_dark_theme
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog


def _resolve_session(settings: AppSettings) -> tuple[str, str] | None:
    """Return ``(mode, pro_path)`` or ``None`` if the user cancelled."""
    if settings.remember_startup_mode:
        mode = settings.startup_mode
        if mode == MODE_OSVVM:
            pro = settings.last_pro_file
            if pro:
                return mode, pro
            # Remembered OSVVM without a .pro — fall through to the dialog.
        else:
            return MODE_NORMAL, ""

    dialog = StartupModeDialog(settings)
    if dialog.exec() != StartupModeDialog.DialogCode.Accepted:
        return None
    dialog.apply_to_settings()
    if dialog.selected_mode == MODE_OSVVM:
        return MODE_OSVVM, dialog.selected_pro_file
    return MODE_NORMAL, ""


def main() -> int:
    # Vor QApplication: unter Linux/WSL XCB bevorzugen (wenn libxcb-cursor
    # vorhanden), damit Surfer per X11-Reparenting eingebettet werden kann.
    ensure_linux_xcb_platform()
    try:
        app = QApplication(sys.argv)
    except Exception as exc:  # noqa: BLE001 - Qt kann hier auch hart abbrechen
        print(f"GHDL Studio could not start: {exc}", file=sys.stderr)
        if sys.platform.startswith("linux"):
            print(
                "Tip (Ubuntu/Debian/WSL): sudo apt install libxcb-cursor0\n"
                "Then start again. Alternatively: export QT_QPA_PLATFORM=wayland",
                file=sys.stderr,
            )
        return 1
    app.setApplicationName("GHDL Studio")
    apply_dark_theme(app)

    settings = AppSettings()
    session = _resolve_session(settings)
    if session is None:
        return 0
    mode, pro_path = session

    if mode == MODE_OSVVM and not pro_path:
        QMessageBox.warning(
            None,
            "No .pro file",
            "OSVVM mode requires a .pro file. Please choose one at startup "
            "or via File → Open .pro…",
        )
        return 1

    window = MainWindow(mode=mode, pro_path=pro_path or None)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
