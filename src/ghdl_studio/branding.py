"""Brand assets (wordmark / window icon) for GHDL Studio."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

_RESOURCES = Path(__file__).resolve().parent / "resources"
_WORDMARK = _RESOURCES / "logo_wordmark.png"
_ICON_PNG = _RESOURCES / "logo_icon.png"
_ICON_ICO = _RESOURCES / "logo_icon.ico"


def resources_dir() -> Path:
    return _RESOURCES


def wordmark_path() -> Path:
    return _WORDMARK


def icon_path() -> Path:
    """Prefer ``.ico`` when present (Windows taskbar); otherwise PNG."""
    if _ICON_ICO.is_file():
        return _ICON_ICO
    return _ICON_PNG


def load_wordmark_pixmap(max_width: int = 420) -> QPixmap | None:
    if not _WORDMARK.is_file():
        return None
    pixmap = QPixmap(str(_WORDMARK))
    if pixmap.isNull():
        return None
    if max_width > 0 and pixmap.width() > max_width:
        return pixmap.scaledToWidth(
            max_width,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap


def load_app_icon() -> QIcon:
    icon = QIcon()
    if _ICON_ICO.is_file():
        icon.addFile(str(_ICON_ICO))
    if _ICON_PNG.is_file():
        icon.addFile(str(_ICON_PNG))
    return icon


def apply_application_icon(app: QApplication) -> None:
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)


def make_wordmark_label(
    parent: QWidget | None = None,
    *,
    max_width: int = 420,
) -> QLabel | None:
    """Return a QLabel showing the wordmark, or ``None`` if the asset is missing."""
    pixmap = load_wordmark_pixmap(max_width=max_width)
    if pixmap is None:
        return None
    label = QLabel(parent)
    label.setPixmap(pixmap)
    label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
    label.setScaledContents(False)
    label.setStyleSheet("background: transparent; border: none;")
    label.setAccessibleName("GHDL Studio")
    return label
