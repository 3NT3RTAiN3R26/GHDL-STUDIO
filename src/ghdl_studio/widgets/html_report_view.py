"""Embedded HTML viewer for OSVVM build reports."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:  # pragma: no cover - optional dependency / slim installs
    QWebEngineView = None  # type: ignore[misc, assignment]
    _HAS_WEBENGINE = False


def webengine_available() -> bool:
    return _HAS_WEBENGINE


class HtmlReportView(QWidget):
    """Show a local HTML report (OSVVM ``build_all.html`` etc.) in a tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: str | None = None

        self._path_label = QLabel("No OSVVM HTML report loaded yet.", self)
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        open_external = QPushButton("Open in browser", self)
        open_external.setToolTip("Open the HTML report in the system browser.")
        open_external.clicked.connect(self._open_external)
        reload_button = QPushButton("Reload", self)
        reload_button.clicked.connect(self.reload)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self._path_label, 1)
        toolbar.addWidget(reload_button)
        toolbar.addWidget(open_external)

        if _HAS_WEBENGINE and QWebEngineView is not None:
            self._engine = "webengine"
            self._view = QWebEngineView(self)
        else:
            self._engine = "textbrowser"
            browser = QTextBrowser(self)
            browser.setOpenExternalLinks(True)
            self._view = browser

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self._view, 1)

    @property
    def report_path(self) -> str | None:
        return self._path

    def load_file(self, path: str) -> bool:
        """Load ``path`` into the viewer. Returns False if the file is missing."""
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            self._path = str(file_path)
            self._path_label.setText(f"Report not found: {file_path}")
            return False

        resolved = str(file_path.resolve())
        self._path = resolved
        url = QUrl.fromLocalFile(resolved)
        self._path_label.setText(f"OSVVM report: {resolved}")

        if self._engine == "webengine":
            self._view.setUrl(url)
        else:
            # QTextBrowser: limited CSS; still useful without QtWebEngine.
            try:
                html = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self._path_label.setText(f"Could not read report: {exc}")
                return False
            self._view.setSearchPaths([str(file_path.parent)])
            self._view.setHtml(html, url)
        return True

    def reload(self) -> None:
        if self._path:
            self.load_file(self._path)

    def _open_external(self) -> None:
        if not self._path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))
