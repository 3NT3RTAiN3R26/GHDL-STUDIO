"""Dialog to edit GHDL generic overrides (``-gNAME=value``)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def normalize_generics(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Build a generics dict from name/value pairs.

    Blank names are skipped. Duplicate names keep the last value.
    """
    result: dict[str, str] = {}
    for name, value in pairs:
        key = name.strip()
        if not key:
            continue
        result[key] = value.strip()
    return result


class GenericsEditorDialog(QDialog):
    """Add / edit / remove ``-gNAME=value`` pairs for Run."""

    def __init__(
        self,
        generics: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generics")
        self.setModal(True)
        self.resize(420, 280)

        self._table = QTableWidget(0, 2, self)
        self._table.setHorizontalHeaderLabels(["Name", "Value"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setToolTip(
            "GHDL generic overrides passed to Run as -gNAME=value. "
            "Leave empty for no -g arguments."
        )

        for name, value in sorted((generics or {}).items()):
            self._append_row(name, value)

        add_btn = QPushButton("Add", self)
        add_btn.clicked.connect(self._on_add)
        remove_btn = QPushButton("Remove", self)
        remove_btn.clicked.connect(self._on_remove)

        row_buttons = QHBoxLayout()
        row_buttons.addWidget(add_btn)
        row_buttons.addWidget(remove_btn)
        row_buttons.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Name–value pairs for GHDL Run (-gNAME=value). Empty list = no -g args.",
                self,
            )
        )
        layout.addWidget(self._table)
        layout.addLayout(row_buttons)
        layout.addWidget(buttons)

        if self._table.rowCount() == 0:
            self._on_add()

    def generics(self) -> dict[str, str]:
        return normalize_generics(self._row_pairs())

    def _row_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            value_item = self._table.item(row, 1)
            name = name_item.text() if name_item else ""
            value = value_item.text() if value_item else ""
            pairs.append((name, value))
        return pairs

    def _append_row(self, name: str = "", value: str = "") -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        name_item = QTableWidgetItem(name)
        value_item = QTableWidgetItem(value)
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        value_item.setFlags(value_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, 0, name_item)
        self._table.setItem(row, 1, value_item)

    def _on_add(self) -> None:
        self._append_row()
        row = self._table.rowCount() - 1
        self._table.setCurrentCell(row, 0)
        self._table.editItem(self._table.item(row, 0))

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        self._table.removeRow(row)

    def _on_accept(self) -> None:
        names = [name.strip() for name, _ in self._row_pairs() if name.strip()]
        if len(names) != len(set(names)):
            QMessageBox.warning(
                self,
                "Generics",
                "Duplicate generic names are not allowed. Rename or remove extras.",
            )
            return
        self.accept()
