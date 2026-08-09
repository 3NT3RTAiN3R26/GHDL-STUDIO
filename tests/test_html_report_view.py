"""Smoke tests for the OSVVM HTML report viewer (QTextBrowser fallback)."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.widgets.html_report_view import HtmlReportView  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_load_file_textbrowser_does_not_call_sethtml_with_url(qapp, tmp_path, monkeypatch):
    html = tmp_path / "build_all.html"
    html.write_text("<html><body><p>ok</p></body></html>", encoding="utf-8")

    # Force the QTextBrowser path even if WebEngine is installed.
    monkeypatch.setattr(
        "ghdl_studio.widgets.html_report_view._HAS_WEBENGINE",
        False,
    )
    view = HtmlReportView()
    assert view._engine == "textbrowser"
    assert view.load_file(str(html)) is True
    assert view.report_path == str(html.resolve())
