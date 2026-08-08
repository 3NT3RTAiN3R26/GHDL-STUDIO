"""Einfacher, in Qt gezeichneter Wellenform-Viewer fuer VCD-Daten."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ghdl_gui.vcd_parser import (
    VcdData,
    VcdSignal,
    choose_time_unit,
    format_femtoseconds_as,
    raw_time_to_femtoseconds,
)

_ROW_HEIGHT = 28
_RULER_HEIGHT = 22
_LABEL_WIDTH = 160
_TARGET_INITIAL_WIDTH_PX = 1200
_TARGET_TICK_SPACING_PX = 90
# GHDL benutzt standardmaessig eine Femtosekunden-Zeitbasis, wodurch Endzeiten
# im Bereich von hunderten Millionen liegen koennen. Qt-Widgets erlauben
# jedoch keine Groessen ueber QWIDGETSIZE_MAX (16777215), daher wird die
# maximale Canvas-Breite hart begrenzt.
_MAX_CANVAS_WIDTH_PX = 16_000_000


def _nice_raw_step(raw_step_estimate: float) -> int:
    """Rundet eine gewuenschte Zeitschrittweite auf einen "runden" 1/2/5-Wert."""
    if raw_step_estimate <= 0:
        return 1
    exponent = math.floor(math.log10(raw_step_estimate))
    base = 10**exponent
    for multiple in (1, 2, 5, 10):
        step = multiple * base
        if step >= raw_step_estimate:
            return max(1, int(round(step)))
    return max(1, int(round(10 * base)))


class _WaveformCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: VcdData | None = None
        self._visible_signals: list[VcdSignal] = []
        self._px_per_unit = 1.0
        self.setMinimumHeight(_ROW_HEIGHT)

    def set_data(self, data: VcdData | None, visible_signals: list[VcdSignal]) -> None:
        self._data = data
        self._visible_signals = visible_signals
        if data is not None and data.end_time > 0:
            self._px_per_unit = _TARGET_INITIAL_WIDTH_PX / data.end_time
        self._update_size()
        self.update()

    def set_zoom(self, px_per_unit: float) -> None:
        if not self._data or self._data.end_time <= 0:
            self._px_per_unit = px_per_unit
        else:
            max_allowed = (_MAX_CANVAS_WIDTH_PX - 40) / self._data.end_time
            self._px_per_unit = max(1e-12, min(max_allowed, px_per_unit))
        self._update_size()
        self.update()

    def _update_size(self) -> None:
        if not self._data:
            self.setMinimumSize(0, 0)
            return
        width = int(self._data.end_time * self._px_per_unit) + 40
        width = max(200, min(width, _MAX_CANVAS_WIDTH_PX))
        height = _RULER_HEIGHT + max(1, len(self._visible_signals)) * _ROW_HEIGHT
        self.setMinimumSize(width, height)
        self.resize(self.minimumSize())

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        if not self._data:
            painter.end()
            return

        self._draw_time_ruler(painter)

        grid_pen = QPen(QColor("#3c3c3c"))
        painter.setPen(grid_pen)
        for row in range(len(self._visible_signals) + 1):
            y = _RULER_HEIGHT + row * _ROW_HEIGHT
            painter.drawLine(0, y, self.width(), y)

        signal_pen = QPen(QColor("#4ec9b0"))
        signal_pen.setWidth(2)
        text_pen = QPen(QColor("#d4d4d4"))
        font = QFont("Consolas", 8)
        painter.setFont(font)

        for row, signal in enumerate(self._visible_signals):
            y_top = _RULER_HEIGHT + row * _ROW_HEIGHT
            y_mid = y_top + _ROW_HEIGHT // 2
            changes = self._data.changes.get(signal.identifier, [])
            if not changes:
                continue

            if signal.size == 1:
                self._draw_bit_signal(painter, signal_pen, changes, y_top)
            else:
                self._draw_bus_signal(painter, signal_pen, text_pen, font, changes, y_mid, y_top)

        painter.end()

    def _draw_time_ruler(self, painter: QPainter) -> None:
        assert self._data is not None
        painter.fillRect(0, 0, self.width(), _RULER_HEIGHT, QColor("#252526"))
        if self._px_per_unit <= 0:
            return

        raw_step = _nice_raw_step(_TARGET_TICK_SPACING_PX / self._px_per_unit)
        total_height = _RULER_HEIGHT + max(1, len(self._visible_signals)) * _ROW_HEIGHT

        # Eine einheitliche Zeiteinheit fuer die gesamte Achse waehlen (statt
        # pro Beschriftung autoskaliert), damit z. B. nicht "0 s" neben
        # "20 ns" steht.
        axis_unit = choose_time_unit(raw_time_to_femtoseconds(raw_step, self._data.timescale))

        tick_pen = QPen(QColor("#4a4a4a"))
        text_pen = QPen(QColor("#9cdcfe"))
        font = QFont("Consolas", 8)
        painter.setFont(font)

        time_value = 0
        # Etwas ueber das Simulationsende hinaus zeichnen, damit die letzte
        # Beschriftung nicht abgeschnitten wirkt.
        end_time = self._data.end_time + raw_step
        while time_value <= end_time:
            x = int(time_value * self._px_per_unit)
            painter.setPen(tick_pen)
            painter.drawLine(x, 0, x, total_height)
            painter.setPen(text_pen)
            label = format_femtoseconds_as(
                raw_time_to_femtoseconds(time_value, self._data.timescale), axis_unit
            )
            painter.drawText(x + 3, _RULER_HEIGHT - 6, label)
            time_value += raw_step

        painter.setPen(QPen(QColor("#5a5a5a")))
        painter.drawLine(0, _RULER_HEIGHT - 1, self.width(), _RULER_HEIGHT - 1)

    def _draw_bit_signal(self, painter, pen, changes, y_top) -> None:
        painter.setPen(pen)
        high_y = y_top + 4
        low_y = y_top + _ROW_HEIGHT - 6
        end_time = self._data.end_time if self._data else 0
        prev_time = 0
        prev_value = changes[0][1] if changes else "0"
        for time, value in changes:
            x_prev = prev_time * self._px_per_unit
            x_cur = time * self._px_per_unit
            y = high_y if prev_value == "1" else low_y
            painter.drawLine(int(x_prev), int(y), int(x_cur), int(y))
            painter.drawLine(int(x_cur), int(high_y), int(x_cur), int(low_y))
            prev_time, prev_value = time, value
        x_prev = prev_time * self._px_per_unit
        x_end = end_time * self._px_per_unit
        y = high_y if prev_value == "1" else low_y
        painter.drawLine(int(x_prev), int(y), int(max(x_end, x_prev)), int(y))

    def _draw_bus_signal(self, painter, pen, text_pen, font, changes, y_mid, y_top) -> None:
        painter.setPen(pen)
        end_time = self._data.end_time if self._data else 0
        segments = list(changes) + [(end_time, None)]
        for i in range(len(segments) - 1):
            time, value = segments[i]
            next_time, _ = segments[i + 1]
            x1 = time * self._px_per_unit
            x2 = max(next_time * self._px_per_unit, x1 + 1)
            top = y_top + 4
            bottom = y_top + _ROW_HEIGHT - 4
            painter.drawLine(int(x1), int(top), int(x1), int(bottom))
            painter.drawLine(int(x1), int(top), int(x2), int(top))
            painter.drawLine(int(x1), int(bottom), int(x2), int(bottom))
            painter.drawLine(int(x2), int(top), int(x2), int(bottom))

            painter.setPen(text_pen)
            label = _format_bus_value(value)
            rect = QRectF(x1 + 2, y_top, max(x2 - x1 - 4, 0), _ROW_HEIGHT)
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(pen)


def _format_bus_value(value: str | None) -> str:
    if value is None:
        return ""
    try:
        return f"0x{int(value, 2):X}"
    except ValueError:
        return value


class WaveformViewer(QWidget):
    """Zeigt Signale einer VCD-Datei als digitale Wellenformen an."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: VcdData | None = None

        self._signal_list = QListWidget(self)
        self._signal_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._signal_list.itemChanged.connect(self._on_visibility_changed)

        signal_header = QLabel("Signal", self)
        signal_header.setFixedHeight(_RULER_HEIGHT)
        signal_header.setStyleSheet(
            "QLabel { background-color: #252526; color: #9cdcfe; padding-left: 4px; }"
        )
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(signal_header)
        left_layout.addWidget(self._signal_list)
        left_container = QWidget(self)
        left_container.setLayout(left_layout)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setWidgetResizable(False)
        self._canvas = _WaveformCanvas()
        self._scroll_area.setWidget(self._canvas)

        zoom_in = QPushButton("Zoom +", self)
        zoom_out = QPushButton("Zoom -", self)
        zoom_in.clicked.connect(lambda: self._canvas.set_zoom(self._canvas._px_per_unit * 1.5))
        zoom_out.clicked.connect(lambda: self._canvas.set_zoom(self._canvas._px_per_unit / 1.5))

        toolbar = QHBoxLayout()
        toolbar.addWidget(zoom_in)
        toolbar.addWidget(zoom_out)
        toolbar.addStretch(1)

        right_layout = QVBoxLayout()
        right_layout.addLayout(toolbar)
        right_layout.addWidget(self._scroll_area)
        right_container = QWidget(self)
        right_container.setLayout(right_layout)

        splitter = QSplitter(self)
        splitter.addWidget(left_container)
        splitter.addWidget(right_container)
        splitter.setSizes([_LABEL_WIDTH, 600])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    def set_data(self, data: VcdData) -> None:
        self._data = data
        self._signal_list.blockSignals(True)
        self._signal_list.clear()
        for signal in data.ordered_signals():
            item = QListWidgetItem(signal.full_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, signal)
            self._signal_list.addItem(item)
        self._signal_list.blockSignals(False)
        self._refresh_canvas()

    def _on_visibility_changed(self, _item: QListWidgetItem) -> None:
        self._refresh_canvas()

    def _refresh_canvas(self) -> None:
        visible: list[VcdSignal] = []
        for i in range(self._signal_list.count()):
            item = self._signal_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                visible.append(item.data(Qt.ItemDataRole.UserRole))
        self._canvas.set_data(self._data, visible)
