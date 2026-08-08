"""Read-only Konsole zur Anzeige der GHDL-Ausgaben."""

from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class LogConsole(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(10000)
        self.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: 'Consolas', 'Courier New', monospace; }"
        )

    def append_command(self, text: str) -> None:
        self._append(text, QColor("#569cd6"))

    def append_output(self, text: str) -> None:
        self._append(text, QColor("#d4d4d4"))

    def append_error(self, text: str) -> None:
        self._append(text, QColor("#f14c4c"))

    def append_success(self, text: str) -> None:
        self._append(text, QColor("#4ec9b0"))

    def _append(self, text: str, color: QColor) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(text if text.endswith("\n") else text + "\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
