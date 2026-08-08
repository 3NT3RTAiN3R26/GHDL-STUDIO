"""Plattformuebergreifendes dunkles Erscheinungsbild fuer GHDL Studio.

Das dunkle Design (angelehnt an typische IDE-/Waveform-Werkzeuge) wird
unabhaengig vom Betriebssystem und vom System-Theme erzwungen, damit die
Oberflaeche unter Windows, Linux und macOS gleich aussieht.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Farbpalette (VS-Code-/IDE-aehnliches Dunkelgrau)
_BG_WINDOW = "#2b2b2b"
_BG_BASE = "#1e1e1e"
_BG_ALT = "#252526"
_BG_BUTTON = "#3c3c3c"
_BG_BUTTON_HOVER = "#4a4a4a"
_BG_BUTTON_PRESSED = "#505050"
_BG_INPUT = "#3c3c3c"
_BG_TAB = "#2d2d2d"
_BG_TAB_SELECTED = "#1e1e1e"
_BG_HEADER = "#333333"
_FG = "#d4d4d4"
_FG_DISABLED = "#808080"
_FG_BRIGHT = "#ffffff"
_BORDER = "#555555"
_ACCENT = "#0e639c"
_ACCENT_HOVER = "#1177bb"
_HIGHLIGHT_TEXT = "#ffffff"
_TOOLTIP_BG = "#2a2d2e"
_TOOLTIP_FG = "#cccccc"


def _qcolor(hex_color: str) -> QColor:
    return QColor(hex_color)


def build_dark_palette() -> QPalette:
    palette = QPalette()
    window = _qcolor(_BG_WINDOW)
    base = _qcolor(_BG_BASE)
    alt = _qcolor(_BG_ALT)
    text = _qcolor(_FG)
    disabled = _qcolor(_FG_DISABLED)
    button = _qcolor(_BG_BUTTON)
    highlight = _qcolor(_ACCENT)
    highlighted_text = _qcolor(_HIGHLIGHT_TEXT)
    bright = _qcolor(_FG_BRIGHT)
    tooltip_bg = _qcolor(_TOOLTIP_BG)
    tooltip_fg = _qcolor(_TOOLTIP_FG)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt)
    palette.setColor(QPalette.ColorRole.ToolTipBase, tooltip_bg)
    palette.setColor(QPalette.ColorRole.ToolTipText, tooltip_fg)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, bright)
    palette.setColor(QPalette.ColorRole.Link, _qcolor(_ACCENT_HOVER))
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, highlighted_text)
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled)

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, _qcolor(_BG_BUTTON))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled)
    return palette


def dark_stylesheet() -> str:
    return f"""
    QWidget {{
        color: {_FG};
        background-color: {_BG_WINDOW};
    }}
    QMainWindow, QDialog, QDockWidget {{
        background-color: {_BG_WINDOW};
    }}
    QToolBar {{
        background-color: {_BG_HEADER};
        border: none;
        border-bottom: 1px solid {_BORDER};
        spacing: 4px;
        padding: 2px;
    }}
    QToolBar QToolButton, QToolBar QPushButton {{
        background-color: {_BG_BUTTON};
        border: 1px solid {_BORDER};
        border-radius: 3px;
        padding: 4px 8px;
        color: {_FG};
    }}
    QToolBar QToolButton:hover, QToolBar QPushButton:hover {{
        background-color: {_BG_BUTTON_HOVER};
        border-color: {_ACCENT_HOVER};
    }}
    QToolBar QToolButton:pressed, QToolBar QPushButton:pressed {{
        background-color: {_BG_BUTTON_PRESSED};
    }}
    QToolBar QLabel {{
        background: transparent;
        color: {_FG};
        padding-left: 6px;
    }}
    QMenuBar {{
        background-color: {_BG_HEADER};
        color: {_FG};
        border-bottom: 1px solid {_BORDER};
    }}
    QMenuBar::item:selected {{
        background-color: {_BG_BUTTON_HOVER};
    }}
    QMenu {{
        background-color: {_BG_ALT};
        color: {_FG};
        border: 1px solid {_BORDER};
    }}
    QMenu::item:selected {{
        background-color: {_ACCENT};
        color: {_HIGHLIGHT_TEXT};
    }}
    QTabWidget::pane {{
        border: 1px solid {_BORDER};
        background-color: {_BG_BASE};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {_BG_TAB};
        color: {_FG};
        border: 1px solid {_BORDER};
        border-bottom: none;
        padding: 6px 12px;
        margin-right: 1px;
    }}
    QTabBar::tab:selected {{
        background-color: {_BG_TAB_SELECTED};
        color: {_FG_BRIGHT};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {_BG_BUTTON_HOVER};
    }}
    QDockWidget {{
        color: {_FG};
        titlebar-close-icon: none;
    }}
    QDockWidget::title {{
        background-color: {_BG_HEADER};
        padding: 4px;
        border: 1px solid {_BORDER};
    }}
    QPushButton {{
        background-color: {_BG_BUTTON};
        color: {_FG};
        border: 1px solid {_BORDER};
        border-radius: 3px;
        padding: 4px 10px;
        min-height: 1.2em;
    }}
    QPushButton:hover {{
        background-color: {_BG_BUTTON_HOVER};
        border-color: {_ACCENT_HOVER};
    }}
    QPushButton:pressed {{
        background-color: {_BG_BUTTON_PRESSED};
    }}
    QPushButton:disabled {{
        color: {_FG_DISABLED};
        background-color: {_BG_ALT};
    }}
    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTextEdit, QListWidget, QTreeWidget, QTableWidget {{
        background-color: {_BG_INPUT};
        color: {_FG};
        border: 1px solid {_BORDER};
        border-radius: 2px;
        selection-background-color: {_ACCENT};
        selection-color: {_HIGHLIGHT_TEXT};
        padding: 2px 4px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 18px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_ALT};
        color: {_FG};
        border: 1px solid {_BORDER};
        selection-background-color: {_ACCENT};
    }}
    QHeaderView::section {{
        background-color: {_BG_HEADER};
        color: {_FG};
        border: 1px solid {_BORDER};
        padding: 3px 6px;
    }}
    QScrollBar:vertical {{
        background: {_BG_BASE};
        width: 12px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {_BG_BUTTON};
        min-height: 24px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {_BG_BUTTON_HOVER};
    }}
    QScrollBar:horizontal {{
        background: {_BG_BASE};
        height: 12px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {_BG_BUTTON};
        min-width: 24px;
        border-radius: 3px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        width: 0;
        height: 0;
    }}
    QStatusBar {{
        background-color: {_BG_HEADER};
        color: {_FG};
        border-top: 1px solid {_BORDER};
    }}
    QToolTip {{
        background-color: {_TOOLTIP_BG};
        color: {_TOOLTIP_FG};
        border: 1px solid {_BORDER};
        padding: 3px;
    }}
    QSplitter::handle {{
        background-color: {_BORDER};
    }}
    QCheckBox, QRadioButton, QLabel {{
        background: transparent;
        color: {_FG};
    }}
    QGroupBox {{
        border: 1px solid {_BORDER};
        border-radius: 3px;
        margin-top: 8px;
        padding-top: 6px;
        color: {_FG};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    """


def apply_dark_theme(app: QApplication) -> None:
    """Erzwingt das dunkle GHDL-Studio-Theme fuer die gesamte Anwendung."""
    app.setStyle("Fusion")
    app.setPalette(build_dark_palette())
    app.setStyleSheet(dark_stylesheet())
