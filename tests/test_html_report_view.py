"""Smoke tests for the OSVVM HTML report viewer (QTextBrowser fallback)."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.widgets.html_report_view import (  # noqa: E402
    HtmlReportView,
    _inject_light_css_into_html,
)


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_load_file_textbrowser_does_not_call_sethtml_with_url(qapp, tmp_path, monkeypatch):
    html = tmp_path / "build_all.html"
    html.write_text(
        "<html><head></head><body><table><tr><th>A</th></tr>"
        "<tr><td>1</td></tr></table></body></html>",
        encoding="utf-8",
    )

    # Force the QTextBrowser path even if WebEngine is installed.
    monkeypatch.setattr(
        "ghdl_studio.widgets.html_report_view._HAS_WEBENGINE",
        False,
    )
    view = HtmlReportView()
    assert view._engine == "textbrowser"
    assert view.load_file(str(html)) is True
    assert view.report_path == str(html.resolve())
    # Document should keep a light default stylesheet for tables.
    css = view._view.document().defaultStyleSheet()
    assert "table" in css
    assert "#ffffff" in css


def test_inject_light_css_preserves_tables():
    html = "<html><head><title>x</title></head><body><table></table></body></html>"
    out = _inject_light_css_into_html(html)
    assert "display: table" in out
    assert "border-collapse" in out
    assert out.index("<style") < out.index("</head>")
