"""Brand asset loading."""

from pathlib import Path

import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from ghdl_studio.branding import (
    icon_path,
    load_app_icon,
    load_wordmark_pixmap,
    make_wordmark_label,
    wordmark_path,
)


@pytest.fixture
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_brand_assets_exist():
    assert wordmark_path().is_file()
    assert icon_path().is_file()
    assert (
        Path(__file__).resolve().parents[1]
        / "src/ghdl_studio/resources/logo_icon.png"
    ).is_file()
    assert (
        Path(__file__).resolve().parents[1]
        / "src/ghdl_studio/resources/logo_icon.ico"
    ).is_file()


def test_load_wordmark_and_icon(qapp: QApplication):
    pixmap = load_wordmark_pixmap(max_width=200)
    assert pixmap is not None
    assert not pixmap.isNull()
    assert pixmap.width() <= 200

    icon = load_app_icon()
    assert not icon.isNull()

    label = make_wordmark_label(None, max_width=180)
    assert label is not None
    assert label.pixmap() is not None
    assert not label.pixmap().isNull()
