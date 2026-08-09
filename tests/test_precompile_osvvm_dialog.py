"""GUI checks for Precompile OSVVM library dialog."""

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QDialog  # noqa: E402

from ghdl_studio.osvvm_commands import PRECOMPILE_ALL, PRECOMPILE_OSVVM  # noqa: E402
from ghdl_studio.settings import AppSettings  # noqa: E402
from ghdl_studio.widgets.precompile_osvvm_dialog import (  # noqa: E402
    PrecompileOsvvmDialog,
)


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return AppSettings()


def test_dialog_defaults_to_osvvm_utility(qapp, settings, tmp_path):
    settings.osvvm_library_directory = str(tmp_path / "osvvm_ghdl")
    dialog = PrecompileOsvvmDialog(settings)
    assert dialog.target == PRECOMPILE_OSVVM
    assert dialog.update_osvvm_lib_path is True
    assert dialog.library_directory == str(tmp_path / "osvvm_ghdl")


def test_dialog_accept_requires_library_directory(qapp, settings, monkeypatch):
    dialog = PrecompileOsvvmDialog(settings)
    dialog._lib_edit.clear()
    warned = {"called": False}

    def _fake_warning(*_args, **_kwargs):
        warned["called"] = True
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        "ghdl_studio.widgets.precompile_osvvm_dialog.QMessageBox.warning",
        _fake_warning,
    )
    dialog._on_accept()
    assert warned["called"]
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_dialog_accept_persists_library_directory(qapp, settings, tmp_path):
    dialog = PrecompileOsvvmDialog(settings)
    dialog._lib_edit.setText(str(tmp_path / "libs"))
    dialog._all_radio.setChecked(True)
    dialog._on_accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.target == PRECOMPILE_ALL
    assert settings.osvvm_library_directory == str(tmp_path / "libs")


def test_guess_from_existing_minus_p_path(qapp, settings, tmp_path):
    ghdl = tmp_path / "osvvm_ghdl" / "VHDL_LIBS" / "GHDL-6.0.0"
    ghdl.mkdir(parents=True)
    # Prefer -P-derived guess when no dedicated library directory is stored.
    settings.osvvm_library_directory = ""
    settings.osvvm_lib_path = str(ghdl)
    dialog = PrecompileOsvvmDialog(settings)
    assert dialog.library_directory == str(tmp_path / "osvvm_ghdl")
