"""Embedded HTML viewer for OSVVM build reports.

Renders reports like a normal browser page: white background, preserved
table layout/CSS. Isolated from the app dark theme so OSVVM HTML looks
the same as \"Open in browser\".
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QFrame,
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

# Injected so Chromium / QTextBrowser do not inherit the dark Fusion palette.
_LIGHT_REPORT_CSS = """
html, body {
  background: #ffffff !important;
  color: #000000 !important;
  color-scheme: light !important;
}
table {
  background: #ffffff !important;
  color: #000000 !important;
  border-collapse: collapse !important;
  display: table !important;
  width: auto !important;
}
thead { display: table-header-group !important; }
tbody { display: table-row-group !important; }
tr { display: table-row !important; }
td, th {
  display: table-cell !important;
  color: #000000 !important;
  border: 1px solid #bbbbbb !important;
  padding: 3px 6px !important;
  vertical-align: middle !important;
}
th { background: #c5d9f1 !important; font-weight: bold !important; }
a { color: #0645ad !important; }
img { background: transparent !important; }
"""


def webengine_available() -> bool:
    return _HAS_WEBENGINE


def _inject_light_css_into_html(html: str) -> str:
    """Ensure a white-page stylesheet is present for QTextBrowser fallback."""
    style_tag = f"<style type=\"text/css\">{_LIGHT_REPORT_CSS}</style>"
    lower = html.lower()
    head_end = lower.find("</head>")
    if head_end >= 0:
        return html[:head_end] + style_tag + html[head_end:]
    body = lower.find("<body")
    if body >= 0:
        return style_tag + html
    return style_tag + html


def _apply_light_palette(widget: QWidget) -> None:
    palette = QPalette(widget.palette())
    white = QColor(255, 255, 255)
    black = QColor(0, 0, 0)
    for role in (
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.AlternateBase,
    ):
        palette.setColor(role, white)
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(role, black)
    palette.setColor(QPalette.ColorRole.Link, QColor(6, 69, 173))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(85, 26, 139))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)


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

        # White document area (toolbar stays on the app theme).
        self._document_frame = QFrame(self)
        self._document_frame.setObjectName("osvvmReportDocument")
        self._document_frame.setStyleSheet(
            "#osvvmReportDocument { background: #ffffff; border: none; }"
        )
        _apply_light_palette(self._document_frame)
        document_layout = QVBoxLayout(self._document_frame)
        document_layout.setContentsMargins(0, 0, 0, 0)

        if _HAS_WEBENGINE and QWebEngineView is not None:
            self._engine = "webengine"
            self._view = QWebEngineView(self._document_frame)
            self._view.setStyleSheet("QWebEngineView { background: #ffffff; }")
            page = self._view.page()
            page.setBackgroundColor(QColor(255, 255, 255))
            self._view.loadFinished.connect(self._on_webengine_load_finished)
        else:
            self._engine = "textbrowser"
            browser = QTextBrowser(self._document_frame)
            browser.setOpenExternalLinks(True)
            _apply_light_palette(browser)
            browser.setStyleSheet(
                "QTextBrowser { background: #ffffff; color: #000000; border: none; }"
            )
            browser.document().setDefaultStyleSheet(_LIGHT_REPORT_CSS)
            self._view = browser

        document_layout.addWidget(self._view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(toolbar)
        layout.addWidget(self._document_frame, 1)

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
            page = self._view.page()
            page.setBackgroundColor(QColor(255, 255, 255))
            self._view.setUrl(url)
        else:
            # QTextBrowser: setHtml() takes only the HTML string (no base URL).
            try:
                html = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self._path_label.setText(f"Could not read report: {exc}")
                return False
            self._view.setSearchPaths([str(file_path.parent)])
            self._view.setHtml(_inject_light_css_into_html(html))
            # Keep local relative links working when possible.
            self._view.document().setBaseUrl(url)
        return True

    def reload(self) -> None:
        if self._path:
            self.load_file(self._path)

    def _on_webengine_load_finished(self, ok: bool) -> None:
        if not ok or self._engine != "webengine":
            return
        # Force light color-scheme and keep tables as tables (browser look).
        css = _LIGHT_REPORT_CSS.replace("\\", "\\\\").replace("`", "\\`")
        script = f"""
        (function() {{
          try {{
            document.documentElement.style.colorScheme = 'light';
            if (document.body) {{
              document.body.style.background = '#ffffff';
              document.body.style.color = '#000000';
            }}
            var id = 'ghdl-studio-osvvm-light';
            var existing = document.getElementById(id);
            if (existing) {{ existing.remove(); }}
            var s = document.createElement('style');
            s.id = id;
            s.type = 'text/css';
            s.appendChild(document.createTextNode(`{css}`));
            (document.head || document.documentElement).appendChild(s);
          }} catch (e) {{}}
        }})();
        """
        self._view.page().runJavaScript(script)

    def _open_external(self) -> None:
        if not self._path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))
