import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.widgets.file_explorer import FileExplorer  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def explorer(qapp, tmp_path):
    widget = FileExplorer()
    a = tmp_path / "a.vhd"
    b = tmp_path / "b.vhd"
    c = tmp_path / "c.vhd"
    for path in (a, b, c):
        path.write_text("entity x is end;")
    widget.add_files([str(a), str(b), str(c)])
    return widget, [str(a.resolve()), str(b.resolve()), str(c.resolve())]


def test_files_preserve_add_order(explorer):
    widget, paths = explorer
    assert widget.files() == paths


def test_move_up_changes_compile_order(explorer):
    widget, paths = explorer
    widget._list.setCurrentRow(1)
    widget._on_move_up()
    assert widget.files() == [paths[1], paths[0], paths[2]]


def test_move_down_changes_compile_order(explorer):
    widget, paths = explorer
    widget._list.setCurrentRow(0)
    widget._on_move_down()
    assert widget.files() == [paths[1], paths[0], paths[2]]


def test_move_up_disabled_at_top(explorer):
    widget, _paths = explorer
    widget._list.setCurrentRow(0)
    widget._update_move_buttons()
    assert not widget._move_up_button.isEnabled()
    assert widget._move_down_button.isEnabled()


def test_move_down_disabled_at_bottom(explorer):
    widget, _paths = explorer
    widget._list.setCurrentRow(2)
    widget._update_move_buttons()
    assert widget._move_up_button.isEnabled()
    assert not widget._move_down_button.isEnabled()


def test_move_emits_files_changed(explorer):
    widget, paths = explorer
    received: list[list[str]] = []
    widget.files_changed.connect(received.append)
    widget._list.setCurrentRow(2)
    widget._on_move_up()
    assert received
    assert received[-1] == [paths[0], paths[2], paths[1]]
