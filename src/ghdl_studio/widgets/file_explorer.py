"""Widget for managing project source files (VHDL and Verilog)."""

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
    """Lists source files added to the project.

    Supports VHDL and Verilog/SystemVerilog. GHDL can only analyse/simulate
    VHDL; Verilog files may still be added (e.g. for mixed-language projects)
    and are skipped during Analyze (see MainWindow._run_analyze). Verilog
    entries are colour-highlighted with a tooltip note.

    List order is the compile order used for ``ghdl -a``.
    """

    files_changed = Signal(list)  # list[str]
    file_double_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemSelectionChanged.connect(self._update_move_buttons)

        add_button = QPushButton("Add file...", self)
        add_button.clicked.connect(self._on_add_files)
        remove_button = QPushButton("Remove", self)
        remove_button.clicked.connect(self._on_remove_selected)

        self._move_up_button = QPushButton("Move up", self)
        self._move_up_button.setToolTip("Move selected file(s) earlier in the compile order")
        self._move_up_button.clicked.connect(self._on_move_up)
        self._move_down_button = QPushButton("Move down", self)
        self._move_down_button.setToolTip("Move selected file(s) later in the compile order")
        self._move_down_button.clicked.connect(self._on_move_down)

        button_row = QHBoxLayout()
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)

        order_row = QHBoxLayout()
        order_row.addWidget(self._move_up_button)
        order_row.addWidget(self._move_down_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addLayout(order_row)
        layout.addWidget(self._list)

        self._update_move_buttons()

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
                    "Note: GHDL cannot analyse Verilog files directly. "
                    "This file will be skipped during the Analyze step."
                )
            else:
                item.setToolTip(normalized)
            self._list.addItem(item)
            existing.add(normalized)
        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _selected_rows(self) -> list[int]:
        return sorted({self._list.row(item) for item in self._list.selectedItems()})

    def _update_move_buttons(self) -> None:
        rows = self._selected_rows()
        count = self._list.count()
        can_move_up = bool(rows) and rows[0] > 0
        can_move_down = bool(rows) and rows[-1] < count - 1
        self._move_up_button.setEnabled(can_move_up)
        self._move_down_button.setEnabled(can_move_down)

    def _move_selected(self, delta: int) -> None:
        rows = self._selected_rows()
        if not rows:
            return

        count = self._list.count()
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == count - 1:
            return

        # Move as a contiguous block relative to neighbours; process in an
        # order that avoids overwriting indices mid-swap.
        ordered = rows if delta > 0 else reversed(rows)
        new_selection: list[int] = []
        for row in ordered:
            target = row + delta
            item = self._list.takeItem(row)
            self._list.insertItem(target, item)
            new_selection.append(target)

        self._list.clearSelection()
        for row in new_selection:
            item = self._list.item(row)
            if item is not None:
                item.setSelected(True)
        if new_selection:
            self._list.setCurrentRow(min(new_selection))

        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _on_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add source files",
            "",
            "VHDL and Verilog files (*.vhd *.vhdl *.v *.sv);;"
            "VHDL files (*.vhd *.vhdl);;"
            "Verilog/SystemVerilog files (*.v *.sv);;"
            "All files (*)",
        )
        if paths:
            self.add_files(paths)

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _on_move_up(self) -> None:
        self._move_selected(-1)

    def _on_move_down(self) -> None:
        self._move_selected(1)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.file_double_clicked.emit(item.data(0))
