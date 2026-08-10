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


def test_add_txt_data_file_is_listed_but_marked(qapp, tmp_path):
    widget = FileExplorer()
    txt = tmp_path / "ref_wave_data.txt"
    txt.write_text("1.0 2.0\n")
    widget.add_files([str(txt)])
    files = widget.files()
    assert files == [str(txt.resolve())]
    item = widget._list.item(0)
    assert "Data/stimulus" in item.toolTip() or "not passed to ghdl" in item.toolTip()


@pytest.fixture
def osvvm_explorer(qapp, tmp_path):
    from ghdl_studio.widgets.file_explorer import MODE_OSVVM

    widget = FileExplorer()
    widget.set_project_mode(MODE_OSVVM)
    a = tmp_path / "a.pro"
    b = tmp_path / "b.pro"
    a.write_text("library osvvm\n")
    b.write_text("library osvvm\n")
    paths = [str(a.resolve()), str(b.resolve())]
    widget.add_files(paths)
    return widget, paths


def test_osvvm_mode_hides_move_buttons(osvvm_explorer):
    widget, _paths = osvvm_explorer
    assert widget._order_row_widget.isHidden()
    widget._update_move_buttons()
    assert not widget._move_up_button.isEnabled()
    assert not widget._move_down_button.isEnabled()


def test_osvvm_mode_rejects_non_pro_files(qapp, tmp_path):
    from ghdl_studio.widgets.file_explorer import MODE_OSVVM

    widget = FileExplorer()
    widget.set_project_mode(MODE_OSVVM)
    vhd = tmp_path / "x.vhd"
    pro = tmp_path / "x.pro"
    vhd.write_text("entity x is end;")
    pro.write_text("library osvvm\n")
    widget.add_files([str(vhd), str(pro)])
    assert widget.files() == [str(pro.resolve())]


def test_osvvm_first_pro_becomes_active(osvvm_explorer):
    widget, paths = osvvm_explorer
    assert widget.active_file() == paths[0]
    assert "(active)" in widget._list.item(0).text()


def test_osvvm_active_is_exclusive(osvvm_explorer):
    from PySide6.QtCore import Qt

    widget, paths = osvvm_explorer
    received: list[str] = []
    widget.active_pro_changed.connect(received.append)
    widget._list.item(1).setCheckState(Qt.CheckState.Checked)
    assert widget.active_file() == paths[1]
    assert received[-1] == paths[1]
    assert widget._list.item(0).checkState() == Qt.CheckState.Unchecked
    assert widget._list.item(1).checkState() == Qt.CheckState.Checked


def test_osvvm_mode_caches_normal_files(qapp, tmp_path):
    from ghdl_studio.widgets.file_explorer import MODE_NORMAL, MODE_OSVVM

    widget = FileExplorer()
    vhd = tmp_path / "dut.vhd"
    pro = tmp_path / "run.pro"
    vhd.write_text("entity dut is end;")
    pro.write_text("library osvvm\n")
    widget.add_files([str(vhd)])
    assert widget.files() == [str(vhd.resolve())]
    widget.set_project_mode(MODE_OSVVM)
    widget.add_files([str(pro)])
    assert widget.files() == [str(pro.resolve())]
    widget.set_project_mode(MODE_NORMAL)
    assert widget.files() == [str(vhd.resolve())]
