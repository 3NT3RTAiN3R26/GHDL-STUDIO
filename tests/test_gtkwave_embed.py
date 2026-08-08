import shutil

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_gui.gtkwave_embed import (  # noqa: E402
    GtkWaveEmbedder,
    find_gtkwave_executable,
    is_embedding_supported,
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_find_gtkwave_executable_matches_shutil_which():
    assert find_gtkwave_executable() == shutil.which("gtkwave")


def test_is_embedding_supported_returns_bool():
    assert isinstance(is_embedding_supported(), bool)


def test_start_with_nonexistent_executable_emits_failed(qapp):
    embedder = GtkWaveEmbedder()
    results = []
    embedder.failed.connect(lambda reason: results.append(("failed", reason)))
    embedder.embedded.connect(lambda widget: results.append(("embedded", widget)))

    parent = QtWidgets.QWidget()
    embedder.start("/nonexistent/gtkwave-binary-that-does-not-exist", "/tmp/does-not-matter.vcd", parent)

    assert len(results) == 1
    assert results[0][0] == "failed"
    assert "GTKWave" in results[0][1]

    embedder.stop()


def test_is_running_false_before_start():
    embedder = GtkWaveEmbedder()
    assert embedder.is_running() is False
