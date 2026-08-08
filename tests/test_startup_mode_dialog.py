"""GUI checks for the Normal vs OSVVM startup dialog."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QDialog  # noqa: E402

from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM  # noqa: E402
from ghdl_studio.settings import AppSettings  # noqa: E402
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # Isolate QSettings from the developer machine.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return AppSettings()


def test_browse_selects_osvvm_mode(qapp, settings, tmp_path, monkeypatch):
    pro = tmp_path / "demo.pro"
    pro.write_text("analyze a.vhd\n", encoding="utf-8")
    dialog = StartupModeDialog(settings)
    dialog._normal_radio.setChecked(True)
    assert dialog.selected_mode == MODE_NORMAL

    monkeypatch.setattr(
        "ghdl_studio.widgets.startup_mode_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(pro), "OSVVM project (*.pro)"),
    )
    dialog._on_browse_pro()
    assert dialog.selected_mode == MODE_OSVVM
    assert dialog.selected_pro_file == str(pro)


def test_accept_with_pro_path_forces_osvvm(qapp, settings, tmp_path):
    pro = tmp_path / "demo.pro"
    pro.write_text("simulate tb\n", encoding="utf-8")
    dialog = StartupModeDialog(settings)
    dialog._normal_radio.setChecked(True)
    dialog._pro_edit.setText(str(pro))
    dialog._on_accept()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    assert dialog.selected_mode == MODE_OSVVM


def test_accept_osvvm_without_pro_stays_open(qapp, settings, monkeypatch):
    dialog = StartupModeDialog(settings)
    dialog._osvvm_radio.setChecked(True)
    dialog._pro_edit.clear()
    # Avoid modal warning blocking the test.
    monkeypatch.setattr(
        "ghdl_studio.widgets.startup_mode_dialog.QMessageBox.warning",
        lambda *args, **kwargs: 0,
    )
    dialog._on_accept()
    assert dialog.result() != int(QDialog.DialogCode.Accepted)
    assert dialog.selected_mode == MODE_OSVVM
