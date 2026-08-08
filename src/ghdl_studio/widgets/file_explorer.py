"""Widget zur Verwaltung der Quelldateien eines Projekts (VHDL und Verilog)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
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

from ghdl_studio.vhdl_scanner import is_verilog_file

_VERILOG_COLOR = QColor("#c586c0")


class FileExplorer(QWidget):
    """Zeigt die dem Projekt hinzugefuegten Quelldateien in einer Liste an.

    Unterstuetzt sowohl VHDL- als auch Verilog/SystemVerilog-Dateien. GHDL
    selbst kann nur VHDL-Dateien analysieren/simulieren; Verilog-Dateien
    koennen dennoch dem Projekt hinzugefuegt werden (z. B. zur Organisation
    gemischtsprachiger Projekte) und werden beim Analyze-Schritt
    uebersprungen (siehe MainWindow._run_analyze). Verilog-Eintraege werden
    farblich hervorgehoben und mit einem Hinweis in der Tooltip markiert.
    """

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
            if is_verilog_file(normalized):
                item.setForeground(_VERILOG_COLOR)
                item.setToolTip(
                    f"{normalized}\n"
                    "Hinweis: GHDL kann Verilog-Dateien nicht direkt analysieren. "
                    "Diese Datei wird beim Analyze-Schritt uebersprungen."
                )
            else:
                item.setToolTip(normalized)
            self._list.addItem(item)
            existing.add(normalized)
        self.files_changed.emit(self.files())

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Quelldateien hinzufuegen",
            "",
            "VHDL- und Verilog-Dateien (*.vhd *.vhdl *.v *.sv);;"
            "VHDL-Dateien (*.vhd *.vhdl);;"
            "Verilog/SystemVerilog-Dateien (*.v *.sv);;"
            "Alle Dateien (*)",
        )
        if paths:
            self.add_files(paths)

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self.files_changed.emit(self.files())

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.file_double_clicked.emit(item.data(0))
