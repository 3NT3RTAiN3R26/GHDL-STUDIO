"""Code editor with line numbers and HDL syntax highlighting."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QTextCursor, QTextDocument, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from ghdl_studio.osvvm_commands import is_pro_file
from ghdl_studio.vhdl_scanner import is_verilog_file, is_vhdl_file
from ghdl_studio.widgets.tcl_highlighter import TclHighlighter
from ghdl_studio.widgets.verilog_highlighter import VerilogHighlighter
from ghdl_studio.widgets.vhdl_highlighter import VhdlHighlighter


class _LineNumberArea(QWidget):
    """Gutter painted to the left of the editor content."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.paint_line_number_area(event)


class CodeEditor(QPlainTextEdit):
    """Plain-text editor with line numbers and VHDL/Verilog/Tcl highlighting."""

    modified_changed = Signal(bool)

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_path = file_path
        self.setFont(QFont("Consolas", 10))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self._find_selections: list[QTextEdit.ExtraSelection] = []

        self._line_number_area = _LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width(0)
        self._highlight_current_line()

        self._highlighter = _highlighter_for_path(file_path, self.document())
        self.setPlainText(Path(file_path).read_text(encoding="utf-8", errors="replace"))
        self.document().setModified(False)
        self.modificationChanged.connect(self.modified_changed)

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, _new_block_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        contents = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(contents.left(), contents.top(), self.line_number_area_width(), contents.height())
        )

    def paint_line_number_area(self, event) -> None:
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#858585"))
                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 6,
                    height,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

        # Separator between gutter and text.
        painter.setPen(QColor("#3c3c3c"))
        painter.drawLine(
            self._line_number_area.width() - 1,
            event.rect().top(),
            self._line_number_area.width() - 1,
            event.rect().bottom(),
        )

    def _highlight_current_line(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = list(self._find_selections)
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#2a2a2a"))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    def highlight_find_matches(self, query: str, *, case_sensitive: bool = False) -> int:
        """Highlight all occurrences of *query*; return the match count."""
        self._find_selections = []
        if not query:
            self._highlight_current_line()
            return 0
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        highlight = QColor("#623d00")
        cursor = QTextCursor(self.document())
        while True:
            cursor = self.document().find(query, cursor, flags)
            if cursor.isNull():
                break
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(highlight)
            selection.cursor = QTextCursor(cursor)
            self._find_selections.append(selection)
        self._highlight_current_line()
        return len(self._find_selections)

    def clear_find_highlights(self) -> None:
        self._find_selections = []
        self._highlight_current_line()

    def find_text(self, query: str, *, flags: QTextDocument.FindFlag | int = 0) -> bool:
        """Find the next occurrence from the current cursor; return True if found."""
        if not query:
            return False
        return bool(self.find(query, QTextDocument.FindFlag(flags)))

    def replace_all(
        self,
        query: str,
        replacement: str,
        *,
        case_sensitive: bool = False,
    ) -> int:
        """Replace every occurrence of *query*; return how many were replaced."""
        if not query:
            return 0
        flags = QTextDocument.FindFlag(0)
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        count = 0
        search = QTextCursor(self.document())
        while True:
            search = self.document().find(query, search, flags)
            if search.isNull():
                break
            search.insertText(replacement)
            count += 1
        cursor.endEditBlock()
        self.highlight_find_matches(query, case_sensitive=case_sensitive)
        return count

    def goto_line(self, line: int, column: int = 1) -> None:
        """Move the cursor to 1-based *line* / *column* and center the view."""
        block_number = max(0, int(line) - 1)
        block = self.document().findBlockByNumber(block_number)
        if not block.isValid():
            block = self.document().lastBlock()
        cursor = QTextCursor(block)
        col = max(1, int(column))
        # Move within the block without wrapping past its end.
        max_col = max(1, block.length())  # includes block separator
        offset = min(col - 1, max(0, max_col - 1))
        if offset:
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,
                QTextCursor.MoveMode.MoveAnchor,
                offset,
            )
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def save(self) -> None:
        Path(self.file_path).write_text(self.toPlainText(), encoding="utf-8")
        self.document().setModified(False)

    @property
    def is_modified(self) -> bool:
        return self.document().isModified()


def _highlighter_for_path(file_path: str, document):
    """Return a syntax highlighter for *file_path*, or ``None`` for plain text."""
    if is_verilog_file(file_path):
        return VerilogHighlighter(document)
    if is_vhdl_file(file_path):
        return VhdlHighlighter(document)
    suffix = Path(file_path).suffix.lower()
    if is_pro_file(file_path) or suffix == ".tcl":
        return TclHighlighter(document)
    return None
