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


def test_log_console_emits_location_on_diagnostic_double_click(qapp, qtbot=None):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from ghdl_studio.ghdl_locations import GhdlLocation

    console = LogConsole()
    console.append_error('bad.vhd:5:3:error: no declaration for "x"')
    received: list = []
    console.location_activated.connect(received.append)

    # Place cursor on the diagnostic line and synthesize a double-click.
    cursor = console.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    console.setTextCursor(cursor)
    block_rect = console.cursorRect(cursor)
    point = QPoint(block_rect.center().x(), block_rect.center().y())
    QTest.mouseDClick(console.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    assert len(received) == 1
    assert received[0] == GhdlLocation(path="bad.vhd", line=5, column=3)
