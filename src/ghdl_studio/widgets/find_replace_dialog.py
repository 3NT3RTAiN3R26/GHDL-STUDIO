"""Find / Replace / Go-to-line dialogs for the code editor."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.widgets.code_editor import CodeEditor


class FindReplaceDialog(QDialog):
    """Modeless-friendly find/replace panel for a :class:`CodeEditor`."""

    def __init__(
        self,
        editor: CodeEditor,
        *,
        replace_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._editor = editor
        self.setWindowTitle("Replace" if replace_mode else "Find")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._find_edit = QLineEdit(self)
        self._find_edit.setPlaceholderText("Find…")
        selected = editor.textCursor().selectedText().replace("\u2029", "\n")
        if selected and "\n" not in selected:
            self._find_edit.setText(selected)

        self._replace_edit = QLineEdit(self)
        self._replace_edit.setPlaceholderText("Replace with…")
        self._replace_edit.setVisible(replace_mode)

        self._case_box = QCheckBox("Case sensitive", self)
        self._status = QLabel("", self)

        find_next = QPushButton("Find next", self)
        find_next.setDefault(True)
        find_next.clicked.connect(self._on_find_next)
        find_prev = QPushButton("Find previous", self)
        find_prev.clicked.connect(self._on_find_prev)

        buttons = QHBoxLayout()
        buttons.addWidget(find_prev)
        buttons.addWidget(find_next)

        if replace_mode:
            replace_one = QPushButton("Replace", self)
            replace_one.clicked.connect(self._on_replace_one)
            replace_all = QPushButton("Replace all", self)
            replace_all.clicked.connect(self._on_replace_all)
            buttons.addWidget(replace_one)
            buttons.addWidget(replace_all)

        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Find", self._find_edit)
        if replace_mode:
            form.addRow("Replace", self._replace_edit)
        layout.addLayout(form)
        layout.addWidget(self._case_box)
        layout.addLayout(buttons)
        layout.addWidget(self._status)

        self._find_edit.returnPressed.connect(self._on_find_next)
        self._find_edit.textChanged.connect(self._on_query_changed)
        self._on_query_changed(self._find_edit.text())

    def _flags(self) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self._case_box.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return flags

    def _on_query_changed(self, text: str) -> None:
        count = self._editor.highlight_find_matches(
            text,
            case_sensitive=self._case_box.isChecked(),
        )
        if not text:
            self._status.setText("")
        elif count == 0:
            self._status.setText("No matches")
        elif count == 1:
            self._status.setText("1 match")
        else:
            self._status.setText(f"{count} matches")

    def _on_find_next(self) -> None:
        query = self._find_edit.text()
        if not query:
            return
        if not self._editor.find_text(query, flags=self._flags()):
            # Wrap: search from start.
            cursor = self._editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._editor.setTextCursor(cursor)
            if not self._editor.find_text(query, flags=self._flags()):
                self._status.setText("No matches")
                return
        self._on_query_changed(query)

    def _on_find_prev(self) -> None:
        query = self._find_edit.text()
        if not query:
            return
        flags = self._flags() | QTextDocument.FindFlag.FindBackward
        if not self._editor.find_text(query, flags=flags):
            cursor = self._editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._editor.setTextCursor(cursor)
            if not self._editor.find_text(query, flags=flags):
                self._status.setText("No matches")
                return
        self._on_query_changed(query)

    def _on_replace_one(self) -> None:
        query = self._find_edit.text()
        if not query:
            return
        cursor = self._editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        matches = (
            selected == query
            if self._case_box.isChecked()
            else selected.lower() == query.lower()
        )
        if matches:
            cursor.insertText(self._replace_edit.text())
        self._on_find_next()

    def _on_replace_all(self) -> None:
        query = self._find_edit.text()
        if not query:
            return
        count = self._editor.replace_all(
            query,
            self._replace_edit.text(),
            case_sensitive=self._case_box.isChecked(),
        )
        self._on_query_changed(query)
        self._status.setText(f"Replaced {count} occurrence(s)")


class GoToLineDialog(QDialog):
    """Ask for a 1-based line number and jump in the editor."""

    def __init__(self, editor: CodeEditor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self.setWindowTitle("Go to line")
        max_line = max(1, editor.blockCount())
        self._spin = QSpinBox(self)
        self._spin.setRange(1, max_line)
        self._spin.setValue(editor.textCursor().blockNumber() + 1)
        self._spin.setSuffix(f" / {max_line}")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Line", self._spin)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._spin.setFocus()

    def selected_line(self) -> int:
        return int(self._spin.value())


def prompt_goto_line(editor: CodeEditor, parent: QWidget | None = None) -> None:
    dialog = GoToLineDialog(editor, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        editor.goto_line(dialog.selected_line())
