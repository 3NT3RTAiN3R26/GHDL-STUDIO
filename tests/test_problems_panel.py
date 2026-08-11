"""Tests for the Problems panel."""

from __future__ import annotations

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.ghdl_locations import GhdlLocation  # noqa: E402
from ghdl_studio.widgets.problems_panel import ProblemsPanel  # noqa: E402


@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_problems_panel_add_clear_and_activate(qapp):
    panel = ProblemsPanel()
    assert panel.problem_count() == 0

    loc = GhdlLocation(
        path="bad.vhd",
        line=5,
        column=3,
        severity="error",
        message='no declaration for "x"',
    )
    emitted: list[GhdlLocation] = []
    panel.location_activated.connect(emitted.append)

    panel.add_diagnostic(loc)
    panel.add_diagnostic(loc)  # duplicate ignored
    assert panel.problem_count() == 1

    warn = GhdlLocation(
        path="bad.vhd",
        line=1,
        column=1,
        severity="warning",
        message="unused",
    )
    panel.add_diagnostic(warn)
    assert panel.problem_count() == 2

    item = panel._tree.topLevelItem(0)
    panel._on_item_activated(item)
    assert emitted and emitted[0] == loc

    panel.clear()
    assert panel.problem_count() == 0
