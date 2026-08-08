import os
import shutil
import subprocess
import sys
import time

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.gtkwave_embed import (  # noqa: E402
    GtkWaveEmbedder,
    _collect_descendant_pids,
    find_gtkwave_executable,
    is_embedding_supported,
    is_xlib_available,
)

_HAS_LIVE_X11 = (
    sys.platform.startswith("linux")
    and bool(os.environ.get("DISPLAY"))
    and is_xlib_available()
    and find_gtkwave_executable() is not None
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


def test_is_xlib_available_matches_real_import():
    import importlib.util

    expected = importlib.util.find_spec("Xlib") is not None
    assert is_xlib_available() is expected


def test_collect_descendant_pids_includes_root_pid():
    pids = _collect_descendant_pids(os.getpid())
    assert os.getpid() in pids


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc ist Linux-spezifisch")
def test_collect_descendant_pids_finds_child_process():
    # Startet einen Kindprozess, der kurz lebt, und prueft, dass seine PID
    # als Nachkomme des aktuellen Prozesses gefunden wird (relevant fuer
    # gtkwave-Wrapper-Skripte, die den eigentlichen GTK-Prozess forken statt
    # sich per exec() selbst zu ersetzen).
    child = subprocess.Popen(["sleep", "2"])
    try:
        time.sleep(0.2)
        pids = _collect_descendant_pids(os.getpid())
        assert child.pid in pids
    finally:
        child.kill()
        child.wait()


@pytest.mark.skipif(
    not _HAS_LIVE_X11, reason="benoetigt einen laufenden X-Server, python-xlib und gtkwave im PATH"
)
def test_x11_full_window_tree_fallback_finds_gtkwave_window(tmp_path):
    """Verifiziert, dass die vollstaendige Fensterbaum-Suche (der Fallback
    fuer Compositor/Fenstermanager, die _NET_CLIENT_LIST nicht pflegen,
    z. B. WSLg) das GTKWave-Fenster tatsaechlich unabhaengig vom
    schnellen EWMH-Pfad findet."""
    from Xlib import display

    from ghdl_studio.gtkwave_embed import _iter_x11_window_tree, _scan_x11_windows

    vcd_path = tmp_path / "empty.vcd"
    vcd_path.write_text(
        "$timescale 1 ns $end\n$scope module top $end\n$upscope $end\n"
        "$enddefinitions $end\n#0\n",
        encoding="utf-8",
    )

    proc = subprocess.Popen([find_gtkwave_executable(), str(vcd_path)])
    try:
        deadline = time.monotonic() + 15
        candidate_pids = _collect_descendant_pids(proc.pid)
        conn = display.Display()
        root = conn.screen().root
        net_wm_pid = conn.intern_atom("_NET_WM_PID")

        found = None
        while time.monotonic() < deadline and found is None:
            found, _ = _scan_x11_windows(_iter_x11_window_tree(root), net_wm_pid, candidate_pids)
            if found is None:
                time.sleep(0.3)
        conn.close()
        assert found is not None, "Fensterbaum-Fallback haette das GTKWave-Fenster finden muessen."
    finally:
        proc.kill()
        proc.wait()
