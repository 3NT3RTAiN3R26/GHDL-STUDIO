"""Einstiegspunkt der Anwendung."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ghdl_studio.surfer_embed import ensure_linux_xcb_platform
from ghdl_studio.main_window import MainWindow
from ghdl_studio.theme import apply_dark_theme


def main() -> int:
    # Vor QApplication: unter Linux/WSL XCB erzwingen, damit Surfer per
    # X11-Reparenting eingebettet werden kann (Wayland unterstuetzt keine
    # Foreign Windows).
    ensure_linux_xcb_platform()
    app = QApplication(sys.argv)
    app.setApplicationName("GHDL Studio")
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
