"""Einstiegspunkt der Anwendung."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ghdl_studio.surfer_embed import ensure_linux_xcb_platform
from ghdl_studio.main_window import MainWindow
from ghdl_studio.theme import apply_dark_theme


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
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
