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


def test_log_console_emits_location_on_diagnostic_click(qapp):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from ghdl_studio.ghdl_locations import GhdlLocation

    console = LogConsole()
    console.resize(640, 200)
    console.show()
    console.append_error('bad.vhd:5:3:error: no declaration for "x"')
    received: list = []
    console.location_activated.connect(received.append)

    cursor = console.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    console.setTextCursor(cursor)
    block_rect = console.cursorRect(cursor)
    point = QPoint(block_rect.center().x(), block_rect.center().y())
    QTest.mouseClick(console.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    assert len(received) == 1
    assert received[0] == GhdlLocation(
        path="bad.vhd",
        line=5,
        column=3,
        severity="error",
        message='no declaration for "x"',
    )


def test_log_console_split_ghdl_format_click(qapp):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from ghdl_studio.ghdl_locations import GhdlLocation

    console = LogConsole()
    console.resize(800, 240)
    console.show()
    path = "/mnt/c/Users/me/GHDL-STUDIO/examples/counter/counter.vhd"
    console.append_error(f"{path}:")
    console.append_error('24:31:error: missing ";" at end of statement')
    received: list = []
    console.location_activated.connect(received.append)

    # Click the second line (line:col:error).
    cursor = console.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.movePosition(QTextCursor.MoveOperation.Up)
    console.setTextCursor(cursor)
    block_rect = console.cursorRect(cursor)
    point = QPoint(max(5, block_rect.center().x()), block_rect.center().y())
    QTest.mouseClick(console.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)

    assert len(received) == 1
    assert received[0] == GhdlLocation(
        path=path,
        line=24,
        column=31,
        severity="error",
        message='missing ";" at end of statement',
    )
