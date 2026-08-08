"""Einbettung von GTKWave als natives Fenster in ein Qt-Widget.

GTKWave bietet keine offizielle Embedding-API. Dieses Modul realisiert die
Einbettung ueber plattformspezifisches "Window Reparenting":

- **Linux/X11**: GTKWave wird als Subprozess gestartet, anschliessend wird
  dessen Top-Level-Fenster ueber die Prozess-ID mittels der EWMH-Properties
  ``_NET_CLIENT_LIST``/``_NET_WM_PID`` gefunden (benoetigt das optionale
  Paket ``python-xlib``) und per ``QWindow.fromWinId()`` /
  ``QWidget.createWindowContainer()`` in die GUI eingebettet.
- **Windows**: analoge Fenstersuche per WinAPI (``EnumWindows`` /
  ``GetWindowThreadProcessId``); zusaetzlich wird die Titelleiste des
  eingebetteten Fensters per ``SetWindowLong`` entfernt.
- **macOS und alle anderen Faelle**: natives Window-Reparenting wird nicht
  unterstuetzt; GTKWave laeuft dann als eigenstaendiges Fenster weiter.

Schlaegt die Einbettung fehl (GTKWave nicht installiert, Timeout beim
Suchen des Fensters, nicht unterstuetzte Plattform, fehlendes
``python-xlib`` unter Linux), wird dies ueber das ``failed``-Signal klar
kommuniziert, sodass die aufrufende GUI auf einen alternativen
Wellenform-Viewer zurueckfallen kann.
"""

from __future__ import annotations

import shutil
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget

_POLL_INTERVAL_MS = 300
_MAX_POLL_ATTEMPTS = 30  # ~9 Sekunden Timeout, GTKWave kann etwas brauchen


def find_gtkwave_executable() -> str | None:
    """Sucht die gtkwave-Executable im PATH und gibt den vollen Pfad zurueck."""
    return shutil.which("gtkwave")


def is_embedding_supported() -> bool:
    """Ob fuer die aktuelle Plattform ueberhaupt ein Embedding-Verfahren existiert."""
    return sys.platform.startswith("linux") or sys.platform.startswith("win")


def _find_window_id_for_pid_x11(pid: int):
    """Einmaliger (nicht-blockierender) Versuch, das Top-Level-Fenster eines
    Prozesses unter X11 per EWMH-Properties zu finden. Gibt ``None`` zurueck,
    falls ``python-xlib`` fehlt, keine X11-Verbindung moeglich ist oder das
    Fenster (noch) nicht gefunden wurde."""
    try:
        from Xlib import X, display  # noqa: PLC0415 - optionale Abhaengigkeit
        from Xlib.error import XError
    except ImportError:
        return None

    try:
        conn = display.Display()
    except Exception:  # noqa: BLE001 - z. B. kein X-Server verfuegbar
        return None

    try:
        root = conn.screen().root
        net_client_list = conn.intern_atom("_NET_CLIENT_LIST")
        net_wm_pid = conn.intern_atom("_NET_WM_PID")
        client_list = root.get_full_property(net_client_list, X.AnyPropertyType)
        if not client_list or not client_list.value:
            return None
        for win_id in client_list.value:
            try:
                window = conn.create_resource_object("window", win_id)
                prop = window.get_full_property(net_wm_pid, X.AnyPropertyType)
                if prop and prop.value and int(prop.value[0]) == pid:
                    return int(win_id)
            except XError:
                continue
    except Exception:  # noqa: BLE001 - robust gegenueber jeglichen X11-Fehlern
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    return None


def _find_hwnd_for_pid_windows(pid: int):
    """Einmaliger Versuch, das sichtbare Top-Level-Fenster eines Prozesses
    unter Windows per WinAPI zu finden."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd, _lparam):
        pid_out = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
        if (
            pid_out.value == pid
            and user32.IsWindowVisible(hwnd)
            and user32.GetWindowTextLengthW(hwnd) > 0
        ):
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(_callback, 0)
    return found[0] if found else None


def _strip_window_decorations_windows(hwnd: int) -> None:
    import ctypes

    gwl_style = -16
    ws_caption = 0x00C00000
    ws_thickframe = 0x00040000
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    style = user32.GetWindowLongW(hwnd, gwl_style)
    style &= ~(ws_caption | ws_thickframe)
    user32.SetWindowLongW(hwnd, gwl_style, style)


class GtkWaveEmbedder(QObject):
    """Startet GTKWave fuer eine VCD-Datei und bettet dessen Fenster ein.

    Verwendung::

        embedder = GtkWaveEmbedder(parent)
        embedder.embedded.connect(on_embedded)   # erhaelt das Container-QWidget
        embedder.failed.connect(on_failed)        # erhaelt eine Fehlermeldung
        embedder.start(gtkwave_path, vcd_path, parent_widget)
    """

    embedded = Signal(QWidget)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._parent_widget: QWidget | None = None
        self._attempts = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll_for_window)

    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning

    def stop(self) -> None:
        self._timer.stop()
        if self._process is not None and self.is_running():
            self._process.kill()
        self._process = None

    def start(self, gtkwave_executable: str, vcd_path: str, parent_widget: QWidget) -> None:
        """Startet GTKWave fuer ``vcd_path`` und versucht anschliessend, das
        entstehende Fenster in ``parent_widget`` einzubetten. Ergebnis wird
        ueber ``embedded``/``failed`` signalisiert."""
        self.stop()

        if not is_embedding_supported():
            self.failed.emit(
                "Fenster-Einbettung wird auf dieser Plattform nicht unterstuetzt "
                "(nur Linux/X11 und Windows). GTKWave wird als eigenstaendiges "
                "Fenster geoeffnet."
            )
            self._launch_standalone(gtkwave_executable, vcd_path)
            return

        self._parent_widget = parent_widget
        self._attempts = 0
        self._process = QProcess(self)
        self._process.start(gtkwave_executable, [vcd_path])
        if not self._process.waitForStarted(5000):
            self.failed.emit("GTKWave konnte nicht gestartet werden. Ist GTKWave installiert und im PATH?")
            self._process = None
            return

        self._timer.start()

    def _launch_standalone(self, gtkwave_executable: str, vcd_path: str) -> None:
        QProcess.startDetached(gtkwave_executable, [vcd_path])

    def _poll_for_window(self) -> None:
        if self._process is None or not self.is_running():
            self._timer.stop()
            self.failed.emit("GTKWave wurde beendet, bevor ein Fenster eingebettet werden konnte.")
            return

        self._attempts += 1
        pid = int(self._process.processId())
        win_id = None
        if sys.platform.startswith("linux"):
            win_id = _find_window_id_for_pid_x11(pid)
        elif sys.platform.startswith("win"):
            win_id = _find_hwnd_for_pid_windows(pid)

        if win_id is not None:
            self._timer.stop()
            self._finish_embedding(win_id)
            return

        if self._attempts >= _MAX_POLL_ATTEMPTS:
            self._timer.stop()
            reason = "GTKWave-Fenster wurde nicht rechtzeitig gefunden (Timeout)."
            if sys.platform.startswith("linux"):
                reason += " Ist das Paket 'python-xlib' installiert?"
            self.failed.emit(reason)

    def _finish_embedding(self, win_id: int) -> None:
        foreign_window = QWindow.fromWinId(win_id)
        if foreign_window is None:
            self.failed.emit("GTKWave-Fenster konnte nicht als Qt-Fenster referenziert werden.")
            return
        if sys.platform.startswith("win"):
            _strip_window_decorations_windows(win_id)
        container = QWidget.createWindowContainer(foreign_window, self._parent_widget)
        self.embedded.emit(container)
