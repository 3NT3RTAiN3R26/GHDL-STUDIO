import os
import shutil
import subprocess
import sys
import time

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from ghdl_studio.surfer_embed import (  # noqa: E402
    SurferEmbedder,
    _collect_descendant_pids,
    _to_win32_long,
    ensure_linux_xcb_platform,
    find_surfer_executable,
    is_embedding_supported,
    is_xlib_available,
)

_HAS_LIVE_X11 = (
    sys.platform.startswith("linux")
    and bool(os.environ.get("DISPLAY"))
    and is_xlib_available()
    and find_surfer_executable() is not None
)


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_find_surfer_executable_matches_shutil_which():
    assert find_surfer_executable() == shutil.which("surfer")


def test_is_embedding_supported_returns_bool():
    assert isinstance(is_embedding_supported(), bool)


def test_start_with_nonexistent_executable_emits_failed(qapp):
    embedder = SurferEmbedder()
    results = []
    embedder.failed.connect(lambda reason: results.append(("failed", reason)))
    embedder.embedded.connect(lambda widget: results.append(("embedded", widget)))

    parent = QtWidgets.QWidget()
    embedder.start("/nonexistent/surfer-binary-that-does-not-exist", "/tmp/does-not-matter.vcd", parent)

    assert len(results) == 1
    assert results[0][0] == "failed"
    assert "Surfer" in results[0][1]

    embedder.stop()


def test_is_running_false_before_start():
    embedder = SurferEmbedder()
    assert embedder.is_running() is False


def test_is_xlib_available_matches_real_import():
    import importlib.util

    expected = importlib.util.find_spec("Xlib") is not None
    assert is_xlib_available() is expected


def test_collect_descendant_pids_includes_root_pid():
    pids = _collect_descendant_pids(os.getpid())
    assert os.getpid() in pids


def test_ensure_linux_xcb_platform_sets_xcb_when_display_present(monkeypatch):
    if not sys.platform.startswith("linux"):
        monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setenv("DISPLAY", ":99")
    ensure_linux_xcb_platform()
    assert os.environ.get("QT_QPA_PLATFORM") == "xcb"


def test_ensure_linux_xcb_platform_respects_existing_override(monkeypatch):
    if not sys.platform.startswith("linux"):
        monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("QT_QPA_PLATFORM", "wayland")
    monkeypatch.setenv("DISPLAY", ":0")
    ensure_linux_xcb_platform()
    assert os.environ.get("QT_QPA_PLATFORM") == "wayland"


def test_to_win32_long_maps_unsigned_styles_into_signed_32bit_range():
    """Reproduziert den Windows-OverflowError bei SetWindowLongW-Arg 3:
    Python-Ints aus Stil-Bitops muessen in signed 32-bit passen."""
    # WS_POPUP|WS_VISIBLE-aehnliche Ausgangswerte und typische Child-Stile
    assert _to_win32_long(0x96000000) == -1778384896
    assert _to_win32_long(0x56000000) == 1442840576
    assert _to_win32_long(-2852126720) == 1442840576  # untere 32 Bit von fehlerhaftem Python-Ergebnis
    assert _to_win32_long(0x50000000 | 0x06000000) == _to_win32_long(0x56000000)

    # Jeder normierte Wert muss als ctypes c_int32 darstellbar sein
    import ctypes

    for raw in (0x00000000, 0x16CF0000, 0x96CF0000, 0xFFFFFFFF, -1, -2852126720, 0x80000000):
        normalized = _to_win32_long(raw)
        assert -0x80000000 <= normalized <= 0x7FFFFFFF
        assert ctypes.c_int32(normalized).value == normalized


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc ist Linux-spezifisch")
def test_collect_descendant_pids_finds_child_process():
    # Startet einen Kindprozess, der kurz lebt, und prueft, dass seine PID
    # als Nachkomme des aktuellen Prozesses gefunden wird (relevant fuer
    # surfer-Wrapper-Skripte, die den eigentlichen GTK-Prozess forken statt
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
    not _HAS_LIVE_X11, reason="benoetigt einen laufenden X-Server, python-xlib und surfer im PATH"
)
def test_x11_full_window_tree_fallback_finds_surfer_window(tmp_path):
    """Verifiziert, dass die vollstaendige Fensterbaum-Suche (der Fallback
    fuer Compositor/Fenstermanager, die _NET_CLIENT_LIST nicht pflegen,
    z. B. WSLg) das Surfer-Fenster tatsaechlich unabhaengig vom
    schnellen EWMH-Pfad findet."""
    from Xlib import display

    from ghdl_studio.surfer_embed import _iter_x11_window_tree, _scan_x11_windows

    vcd_path = tmp_path / "minimal.vcd"
    # Mindestens ein Signal noetig - sonst beendet Surfer sofort mit
    # "No symbols in VCD file..nothing to do!" und oeffnet kein Fenster.
    vcd_path.write_text(
        "$timescale 1 ns $end\n"
        "$scope module top $end\n"
        "$var wire 1 ! clk $end\n"
        "$upscope $end\n"
        "$enddefinitions $end\n"
        "#0\n$dumpvars\n1!\n$end\n"
        "#10\n0!\n#20\n1!\n",
        encoding="utf-8",
    )

    proc = subprocess.Popen([find_surfer_executable(), str(vcd_path)])
    try:
        deadline = time.monotonic() + 15
        conn = display.Display()
        root = conn.screen().root
        net_wm_pid = conn.intern_atom("_NET_WM_PID")

        found = None
        while time.monotonic() < deadline and found is None:
            if proc.poll() is not None:
                break
            candidate_pids = _collect_descendant_pids(proc.pid)
            found, _ = _scan_x11_windows(_iter_x11_window_tree(root), net_wm_pid, candidate_pids)
            if found is None:
                time.sleep(0.3)
        conn.close()
        assert found is not None, "Fensterbaum-Fallback haette das Surfer-Fenster finden muessen."
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
