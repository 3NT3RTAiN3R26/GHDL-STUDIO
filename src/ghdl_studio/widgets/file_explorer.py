"""Widget for managing project source and data files (VHDL, Verilog, .txt, …).

In OSVVM mode the same dock lists ``.pro`` scripts, with an exclusive
“active” check to choose which script Build uses.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
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

from ghdl_studio.osvvm_commands import is_pro_file
from ghdl_studio.vhdl_scanner import is_data_file, is_verilog_file, is_vhdl_file

MODE_NORMAL = "normal"
MODE_OSVVM = "osvvm"

_VERILOG_COLOR = QColor("#c586c0")
_DATA_COLOR = QColor("#ce9178")
_PRO_COLOR = QColor("#4ec9b0")
_PRO_ACTIVE_COLOR = QColor("#4fc1ff")


class FileExplorer(QWidget):
    """Lists files added to the project.

    **Normal mode:** VHDL, Verilog/SystemVerilog, and data/stimulus files.
    Only VHDL is passed to ``ghdl -a``. List order is the compile order.

    **OSVVM mode:** ``.pro`` project scripts. Exactly one entry is marked
    active (checkable) and used for Build. Move up/down is hidden.
    """

    files_changed = Signal(list)  # list[str]
    file_double_clicked = Signal(str)
    active_pro_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = MODE_NORMAL
        self._cached_files: dict[str, list[str]] = {MODE_NORMAL: [], MODE_OSVVM: []}
        self._cached_active: dict[str, str] = {MODE_NORMAL: "", MODE_OSVVM: ""}
        self._updating_checks = False

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._list.itemSelectionChanged.connect(self._update_move_buttons)
        self._list.itemChanged.connect(self._on_item_changed)

        self._add_button = QPushButton("Add file...", self)
        self._add_button.clicked.connect(self._on_add_files)
        remove_button = QPushButton("Remove", self)
        remove_button.clicked.connect(self._on_remove_selected)

        self._move_up_button = QPushButton("Move up", self)
        self._move_up_button.setToolTip("Move selected file(s) earlier in the compile order")
        self._move_up_button.clicked.connect(self._on_move_up)
        self._move_down_button = QPushButton("Move down", self)
        self._move_down_button.setToolTip("Move selected file(s) later in the compile order")
        self._move_down_button.clicked.connect(self._on_move_down)

        button_row = QHBoxLayout()
        button_row.addWidget(self._add_button)
        button_row.addWidget(remove_button)

        self._order_row_widget = QWidget(self)
        order_row = QHBoxLayout(self._order_row_widget)
        order_row.setContentsMargins(0, 0, 0, 0)
        order_row.addWidget(self._move_up_button)
        order_row.addWidget(self._move_down_button)

        layout = QVBoxLayout(self)
        layout.addLayout(button_row)
        layout.addWidget(self._order_row_widget)
        layout.addWidget(self._list)

        self._update_move_buttons()

    def project_mode(self) -> str:
        return self._mode

    def set_project_mode(self, mode: str) -> None:
        """Switch between Normal HDL files and OSVVM ``.pro`` scripts."""
        if mode not in (MODE_NORMAL, MODE_OSVVM):
            mode = MODE_NORMAL
        if mode == self._mode:
            self._apply_mode_chrome()
            return

        self._cached_files[self._mode] = self.files()
        self._cached_active[self._mode] = self.active_file()
        self._mode = mode
        self._reload_from_cache()
        self._apply_mode_chrome()

    def _apply_mode_chrome(self) -> None:
        osvvm = self._mode == MODE_OSVVM
        self._order_row_widget.setVisible(not osvvm)
        self._add_button.setText("Add .pro..." if osvvm else "Add file...")
        self._add_button.setToolTip(
            "Add OSVVM .pro project script(s)"
            if osvvm
            else "Add VHDL / Verilog / data files to the project"
        )
        self._update_move_buttons()

    def _reload_from_cache(self) -> None:
        self._updating_checks = True
        self._list.clear()
        self._updating_checks = False
        paths = list(self._cached_files.get(self._mode, []))
        active = self._cached_active.get(self._mode, "")
        if paths:
            self.add_files(paths)
            if self._mode == MODE_OSVVM:
                self.set_active_file(active or paths[0])

    def files(self) -> list[str]:
        return [self._list.item(i).data(0) for i in range(self._list.count())]

    def clear_files(self) -> None:
        self._updating_checks = True
        self._list.clear()
        self._updating_checks = False
        self._cached_files[self._mode] = []
        self._cached_active[self._mode] = ""
        self.files_changed.emit([])
        self._update_move_buttons()

    def active_file(self) -> str:
        """Return the active ``.pro`` path in OSVVM mode (else empty)."""
        if self._mode != MODE_OSVVM:
            return ""
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                return str(item.data(0) or "")
        return ""

    def set_active_file(self, path: str) -> None:
        """Mark *path* as the exclusive active ``.pro`` (OSVVM mode)."""
        if self._mode != MODE_OSVVM or not path:
            return
        target = str(Path(path).expanduser().resolve())
        self._updating_checks = True
        found = False
        for index in range(self._list.count()):
            item = self._list.item(index)
            item_path = str(item.data(0) or "")
            checked = item_path == target
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self._style_pro_item(item, active=checked)
            found = found or checked
        self._updating_checks = False
        if found and self._cached_active.get(MODE_OSVVM) != target:
            self._cached_active[MODE_OSVVM] = target
            self.active_pro_changed.emit(target)
        elif found:
            self._cached_active[MODE_OSVVM] = target

    def add_files(self, paths: list[str]) -> None:
        existing = set(self.files())
        added: list[str] = []
        for path in paths:
            normalized = str(Path(path).expanduser().resolve())
            if normalized in existing:
                continue
            if self._mode == MODE_OSVVM and not is_pro_file(normalized):
                continue
            item = QListWidgetItem(Path(normalized).name)
            item.setData(0, normalized)
            if self._mode == MODE_OSVVM:
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                self._style_pro_item(item, active=False)
            elif is_verilog_file(normalized):
                item.setForeground(_VERILOG_COLOR)
                item.setToolTip(
                    f"{normalized}\n"
                    "Note: GHDL cannot analyse Verilog files directly. "
                    "This file will be skipped during the Analyze step."
                )
            elif is_data_file(normalized):
                item.setForeground(_DATA_COLOR)
                item.setToolTip(
                    f"{normalized}\n"
                    "Data/stimulus file — not passed to ghdl -a. "
                    "Keep it in the project so the project root is detected; "
                    "testbenches often open paths such as ../input/*.txt "
                    "relative to the output directory."
                )
            elif is_vhdl_file(normalized):
                item.setToolTip(normalized)
            else:
                item.setForeground(_DATA_COLOR)
                item.setToolTip(
                    f"{normalized}\n"
                    "Non-HDL file — not passed to ghdl -a."
                )
            self._list.addItem(item)
            existing.add(normalized)
            added.append(normalized)

        if added and self._mode == MODE_OSVVM and not self.active_file():
            self.set_active_file(added[0])

        self._cached_files[self._mode] = self.files()
        if self._mode == MODE_OSVVM:
            self._cached_active[MODE_OSVVM] = self.active_file()
        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _style_pro_item(self, item: QListWidgetItem, *, active: bool) -> None:
        path = str(item.data(0) or "")
        item.setForeground(_PRO_ACTIVE_COLOR if active else _PRO_COLOR)
        marker = " (active)" if active else ""
        item.setText(f"{Path(path).name}{marker}")
        item.setToolTip(
            f"{path}\n"
            + (
                "Active OSVVM .pro — used by Simulation → Build .pro.\n"
                "Double-click to open in the Editor tab."
                if active
                else "OSVVM .pro script. Check the box to make it active for Build.\n"
                "Double-click to open in the Editor tab."
            )
        )

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating_checks or self._mode != MODE_OSVVM:
            return
        if item.checkState() == Qt.CheckState.Checked:
            path = str(item.data(0) or "")
            self._updating_checks = True
            for index in range(self._list.count()):
                other = self._list.item(index)
                is_active = other is item
                other.setCheckState(
                    Qt.CheckState.Checked if is_active else Qt.CheckState.Unchecked
                )
                self._style_pro_item(other, active=is_active)
            self._updating_checks = False
            self._cached_active[MODE_OSVVM] = path
            self.active_pro_changed.emit(path)
            return

        # Prevent leaving the list with no active .pro.
        if self._list.count() and not self.active_file():
            self.set_active_file(str(item.data(0) or self.files()[0]))

    def _selected_rows(self) -> list[int]:
        return sorted({self._list.row(item) for item in self._list.selectedItems()})

    def _update_move_buttons(self) -> None:
        if self._mode == MODE_OSVVM:
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)
            return
        rows = self._selected_rows()
        count = self._list.count()
        can_move_up = bool(rows) and rows[0] > 0
        can_move_down = bool(rows) and rows[-1] < count - 1
        self._move_up_button.setEnabled(can_move_up)
        self._move_down_button.setEnabled(can_move_down)

    def _move_selected(self, delta: int) -> None:
        if self._mode == MODE_OSVVM:
            return
        rows = self._selected_rows()
        if not rows:
            return

        count = self._list.count()
        if delta < 0 and rows[0] == 0:
            return
        if delta > 0 and rows[-1] == count - 1:
            return

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

        self._cached_files[self._mode] = self.files()
        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _on_add_files(self) -> None:
        if self._mode == MODE_OSVVM:
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Add OSVVM .pro file(s)",
                "",
                "OSVVM project (*.pro);;All files (*)",
            )
        else:
            paths, _ = QFileDialog.getOpenFileNames(
                self,
                "Add project files",
                "",
                "HDL and data files (*.vhd *.vhdl *.v *.sv *.txt *.csv *.dat *.hex *.mem);;"
                "VHDL files (*.vhd *.vhdl);;"
                "Verilog/SystemVerilog files (*.v *.sv);;"
                "Data / stimulus files (*.txt *.csv *.dat *.hex *.mem *.bin *.yml *.yaml);;"
                "All files (*)",
            )
        if paths:
            self.add_files(paths)

    def _on_remove_selected(self) -> None:
        removed_active = False
        active = self.active_file()
        for item in list(self._list.selectedItems()):
            path = str(item.data(0) or "")
            if path == active:
                removed_active = True
            self._list.takeItem(self._list.row(item))
        self._cached_files[self._mode] = self.files()
        if self._mode == MODE_OSVVM:
            remaining = self.files()
            if removed_active and remaining:
                self.set_active_file(remaining[0])
            elif not remaining:
                self._cached_active[MODE_OSVVM] = ""
                self.active_pro_changed.emit("")
            else:
                self._cached_active[MODE_OSVVM] = self.active_file()
        self.files_changed.emit(self.files())
        self._update_move_buttons()

    def _on_move_up(self) -> None:
        self._move_selected(-1)

    def _on_move_down(self) -> None:
        self._move_selected(1)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.file_double_clicked.emit(item.data(0))
