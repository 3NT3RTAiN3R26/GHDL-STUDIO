"""Einstiegspunkt der Anwendung."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ghdl_studio.main_window import MainWindow
from ghdl_studio.theme import apply_dark_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GHDL Studio")
    apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
