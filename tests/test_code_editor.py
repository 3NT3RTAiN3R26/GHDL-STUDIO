"""Tests for the code editor (line numbers + HDL highlighters)."""

import pytest

QtGui = pytest.importorskip("PySide6.QtGui")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.widgets.code_editor import CodeEditor, _highlighter_for_path  # noqa: E402
from ghdl_studio.widgets.tcl_highlighter import TclHighlighter  # noqa: E402
from ghdl_studio.widgets.verilog_highlighter import VerilogHighlighter  # noqa: E402
from ghdl_studio.widgets.vhdl_highlighter import VhdlHighlighter  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_highlighter_for_path_selects_vhdl_and_verilog(qapp, tmp_path):
    doc = QtGui.QTextDocument()
    assert isinstance(_highlighter_for_path(str(tmp_path / "a.vhd"), doc), VhdlHighlighter)
    assert isinstance(_highlighter_for_path(str(tmp_path / "b.vhdl"), doc), VhdlHighlighter)
    assert isinstance(_highlighter_for_path(str(tmp_path / "c.v"), doc), VerilogHighlighter)
    assert isinstance(_highlighter_for_path(str(tmp_path / "d.sv"), doc), VerilogHighlighter)
    assert isinstance(_highlighter_for_path(str(tmp_path / "run.pro"), doc), TclHighlighter)
    assert isinstance(_highlighter_for_path(str(tmp_path / "StartUp.tcl"), doc), TclHighlighter)
    assert _highlighter_for_path(str(tmp_path / "notes.txt"), doc) is None


def test_code_editor_uses_tcl_highlighter_for_pro(qapp, tmp_path):
    path = tmp_path / "run.pro"
    path.write_text(
        "# OSVVM\n"
        "SetVHDLVersion 2008\n"
        "if {[info exists ::x]} { set y 1 }\n"
        "analyze adder.vhd\n",
        encoding="utf-8",
    )
    editor = CodeEditor(str(path))
    assert isinstance(editor._highlighter, TclHighlighter)


def test_tcl_highlighter_rehighlights_without_error(qapp):
    doc = QtGui.QTextDocument()
    highlighter = TclHighlighter(doc)
    doc.setPlainText(
        "# comment\n"
        "set x 1\n"
        'puts "hello $x"\n'
        "analyze foo.vhd\n"
    )
    highlighter.rehighlight()
    assert doc.blockCount() >= 3


def test_code_editor_shows_line_number_gutter(qapp, tmp_path):
    path = tmp_path / "counter.vhd"
    path.write_text(
        "entity counter is\n"
        "end entity;\n"
        "-- comment\n",
        encoding="utf-8",
    )
    editor = CodeEditor(str(path))
    assert editor.line_number_area_width() >= 12
    assert editor.blockCount() >= 3
    assert isinstance(editor._highlighter, VhdlHighlighter)
    # Viewport left margin reserves space for the gutter.
    assert editor.viewportMargins().left() == editor.line_number_area_width()


def test_code_editor_uses_verilog_highlighter(qapp, tmp_path):
    path = tmp_path / "top.v"
    path.write_text("module top;\nendmodule\n", encoding="utf-8")
    editor = CodeEditor(str(path))
    assert isinstance(editor._highlighter, VerilogHighlighter)


def test_vhdl_highlighter_rehighlights_without_error(qapp):
    doc = QtGui.QTextDocument()
    highlighter = VhdlHighlighter(doc)
    doc.setPlainText('entity e is\n  signal x : std_logic := \'1\'; -- hello\nend entity;')
    highlighter.rehighlight()
    assert doc.blockCount() >= 2


def test_verilog_highlighter_handles_block_comments(qapp):
    doc = QtGui.QTextDocument()
    highlighter = VerilogHighlighter(doc)
    doc.setPlainText("module top;\n/* block\ncomment */\nendmodule\n")
    highlighter.rehighlight()
    assert doc.blockCount() >= 3


def test_code_editor_goto_line(qapp, tmp_path):
    path = tmp_path / "n.vhd"
    path.write_text("line1\nline2\nline3abc\n", encoding="utf-8")
    editor = CodeEditor(str(path))
    editor.goto_line(3, 5)
    cursor = editor.textCursor()
    assert cursor.blockNumber() == 2
    # Column 5 within "line3abc" → index 4
    assert cursor.positionInBlock() == 4
