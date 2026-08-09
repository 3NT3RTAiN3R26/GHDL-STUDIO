"""LogConsole API used by MainWindow process callbacks."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.widgets.log_console import LogConsole  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_log_console_has_main_window_append_api(qapp):
    console = LogConsole()
    console.append_command("$ ghdl --clean")
    console.append_output("note")
    console.append_warning("warn")
    console.append_error("boom")
    console.append_success("[Clean] finished successfully (exit code 0).")
    text = console.toPlainText()
    assert "$ ghdl --clean" in text
    assert "note" in text
    assert "warn" in text
    assert "Error: boom" in text
    assert "[Clean] finished successfully" in text
