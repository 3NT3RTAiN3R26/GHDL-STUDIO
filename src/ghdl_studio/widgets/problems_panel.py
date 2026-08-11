"""Problems panel listing GHDL diagnostics (clickable)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ghdl_studio.ghdl_locations import GhdlLocation


class ProblemsPanel(QWidget):
    """Dockable list of GHDL ``file:line:col:severity`` diagnostics."""

    location_activated = Signal(object)  # GhdlLocation

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tree = QTreeWidget(self)
        self._tree.setObjectName("problems_tree")
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(["Severity", "File", "Line", "Col", "Message"])
        self._tree.setRootIsDecorated(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)
        self._tree.itemActivated.connect(self._on_item_activated)
        self._tree.itemDoubleClicked.connect(self._on_item_activated)
        self._tree.setToolTip("Double-click a problem to open it in the Editor.")

        self._count_label = QLabel("0 problems", self)

        clear_btn = QPushButton("Clear", self)
        clear_btn.clicked.connect(self.clear)

        header = QHBoxLayout()
        header.addWidget(self._count_label, 1)
        header.addWidget(clear_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(header)
        layout.addWidget(self._tree)

    def clear(self) -> None:
        self._tree.clear()
        self._refresh_count()

    def problem_count(self) -> int:
        return self._tree.topLevelItemCount()

    def add_diagnostic(self, location: GhdlLocation) -> None:
        """Append a diagnostic; duplicates (same path/line/col/message) are skipped."""
        path_name = location.path
        key = (
            location.path,
            location.line,
            location.column,
            location.severity.lower(),
            location.message,
        )
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            stored = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(stored, GhdlLocation):
                existing = (
                    stored.path,
                    stored.line,
                    stored.column,
                    stored.severity.lower(),
                    stored.message,
                )
                if existing == key:
                    return

        item = QTreeWidgetItem(
            [
                location.severity.lower() or "error",
                path_name,
                str(location.line),
                str(location.column),
                location.message,
            ]
        )
        item.setData(0, Qt.ItemDataRole.UserRole, location)
        item.setToolTip(4, location.message or f"{location.path}:{location.line}")
        self._tree.addTopLevelItem(item)
        self._refresh_count()

    def _refresh_count(self) -> None:
        n = self.problem_count()
        if n == 0:
            self._count_label.setText("0 problems")
        elif n == 1:
            self._count_label.setText("1 problem")
        else:
            self._count_label.setText(f"{n} problems")

    def _on_item_activated(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        location = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(location, GhdlLocation):
            self.location_activated.emit(location)
