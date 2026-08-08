"""Einfacher Texteditor mit VHDL-Syntax-Highlighting fuer geoeffnete Dateien."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from ghdl_gui.widgets.vhdl_highlighter import VhdlHighlighter


class CodeEditor(QPlainTextEdit):
    modified_changed = Signal(bool)

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self.setFont(QFont("Consolas", 10))
        self._highlighter = VhdlHighlighter(self.document())
        self.setPlainText(Path(file_path).read_text(encoding="utf-8", errors="replace"))
        self.document().setModified(False)
        self.modificationChanged.connect(self.modified_changed)

    def save(self) -> None:
        Path(self.file_path).write_text(self.toPlainText(), encoding="utf-8")
        self.document().setModified(False)

    @property
    def is_modified(self) -> bool:
        return self.document().isModified()
