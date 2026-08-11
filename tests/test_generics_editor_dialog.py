"""Tests for the Generics editor (simulation bar / -gNAME=value)."""

from __future__ import annotations

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtWidgets import QDialog, QTableWidgetItem  # noqa: E402

from ghdl_studio.widgets.generics_editor_dialog import (  # noqa: E402
    GenericsEditorDialog,
    normalize_generics,
)


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app


def test_normalize_generics_skips_blank_names():
    assert normalize_generics([("WIDTH", "8"), ("", "1"), ("  ", "x")]) == {
        "WIDTH": "8"
    }


def test_normalize_generics_strips_and_last_wins():
    assert normalize_generics(
        [(" WIDTH ", " 4 "), ("DEPTH", "16"), ("WIDTH", "8")]
    ) == {"WIDTH": "8", "DEPTH": "16"}


def test_normalize_generics_empty():
    assert normalize_generics([]) == {}
    assert normalize_generics([("", ""), ("  ", " ")]) == {}


def test_dialog_loads_and_returns_generics(qapp):
    dialog = GenericsEditorDialog({"WIDTH": "8", "DEPTH": "16"})
    assert dialog.generics() == {"WIDTH": "8", "DEPTH": "16"}
    assert dialog._table.rowCount() == 2


def test_dialog_add_remove_and_accept(qapp):
    dialog = GenericsEditorDialog({})
    # Constructor adds one blank row when empty.
    assert dialog._table.rowCount() >= 1
    dialog._table.setItem(0, 0, QTableWidgetItem("CLK_HZ"))
    dialog._table.setItem(0, 1, QTableWidgetItem("100000000"))
    dialog._on_add()
    last = dialog._table.rowCount() - 1
    dialog._table.setItem(last, 0, QTableWidgetItem("WIDTH"))
    dialog._table.setItem(last, 1, QTableWidgetItem("4"))
    assert dialog.generics() == {"CLK_HZ": "100000000", "WIDTH": "4"}

    dialog._table.setCurrentCell(0, 0)
    dialog._on_remove()
    assert dialog.generics() == {"WIDTH": "4"}

    dialog._on_accept()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_dialog_rejects_duplicate_names(qapp, monkeypatch):
    dialog = GenericsEditorDialog({})
    dialog._table.setItem(0, 0, QTableWidgetItem("WIDTH"))
    dialog._table.setItem(0, 1, QTableWidgetItem("4"))
    dialog._on_add()
    last = dialog._table.rowCount() - 1
    dialog._table.setItem(last, 0, QTableWidgetItem("WIDTH"))
    dialog._table.setItem(last, 1, QTableWidgetItem("8"))

    warned: list[str] = []

    def _fake_warning(parent, title, text):
        warned.append(text)
        return QtWidgets.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        "ghdl_studio.widgets.generics_editor_dialog.QMessageBox.warning",
        _fake_warning,
    )
    dialog._on_accept()
    assert warned
    assert dialog.result() != int(QDialog.DialogCode.Accepted)
