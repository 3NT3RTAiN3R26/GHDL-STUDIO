import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.theme import apply_dark_theme, build_dark_palette, dark_stylesheet  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_build_dark_palette_sets_dark_window_color():
    palette = build_dark_palette()
    window_color = palette.color(palette.ColorRole.Window)
    # Dunkles Grau, nicht helles System-Theme
    assert window_color.lightness() < 80


def test_dark_stylesheet_mentions_core_widgets():
    sheet = dark_stylesheet()
    assert "QMainWindow" in sheet
    assert "QToolBar" in sheet
    assert "QTabBar::tab" in sheet
    assert "#1e1e1e" in sheet


def test_apply_dark_theme_sets_fusion_and_stylesheet(qapp):
    apply_dark_theme(qapp)
    # setStyleSheet() wrappt den Style als QStyleSheetStyle; die Basis bleibt Fusion.
    assert "Fusion" in QtWidgets.QStyleFactory.keys()
    assert qapp.styleSheet()
    assert "#1e1e1e" in qapp.styleSheet()
    assert qapp.palette().color(qapp.palette().ColorRole.Window).lightness() < 80
