"""Widget zur Verwaltung der VHDL-Quelldateien eines Projekts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FileExplorer(QWidget):
    """Zeigt die dem Projekt hinzugefuegten VHDL-Dateien in einer Liste an."""

    files_changed = Signal(list)  # list[str]
    file_double_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)

        add_button = QPushButton("Datei hinzufuegen...", self)
        add_button.clicked.connect(self._on_add_files)
        remove_button = QPushButton("Entfernen", self)
        remove_button.clicked.connect(self._on_remove_selected)

        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self._list)

    def files(self) -> list[str]:
        return [self._list.item(i).data(0) for i in range(self._list.count())]

    def add_files(self, paths: list[str]) -> None:
        existing = set(self.files())
        for path in paths:
            normalized = str(Path(path).resolve())
            if normalized in existing:
                continue
            item = QListWidgetItem(Path(normalized).name)
            item.setData(0, normalized)
            item.setToolTip(normalized)
            self._list.addItem(item)
            existing.add(normalized)
        self.files_changed.emit(self.files())

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "VHDL-Dateien hinzufuegen",
            "",
            "VHDL-Dateien (*.vhd *.vhdl);;Alle Dateien (*)",
        )
        if paths:
            self.add_files(paths)

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self.files_changed.emit(self.files())

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.file_double_clicked.emit(item.data(0))
