"""Einbettung von GTKWave als natives Fenster in ein Qt-Widget.

GTKWave bietet keine offizielle Embedding-API. Dieses Modul realisiert die
Einbettung ueber plattformspezifisches "Window Reparenting":

- **Linux/X11**: GTKWave wird als Subprozess gestartet, anschliessend wird
  dessen Top-Level-Fenster gefunden (benoetigt das optionale Paket
  ``python-xlib``) und per ``QWindow.fromWinId()`` /
  ``QWidget.createWindowContainer()`` in die GUI eingebettet. Die Suche
  versucht zuerst einen exakten Treffer ueber ``_NET_WM_PID`` gegen die
  PID des gestarteten Prozesses *oder* eine seiner (rekursiven)
  Kindprozess-PIDs; schlaegt der schnelle Pfad ueber die EWMH-Property
  ``_NET_CLIENT_LIST`` fehl (z. B. weil der Compositor unter WSLg diese
  nicht zuverlaessig pflegt), wird zusaetzlich der komplette
  X11-Fensterbaum ab dem Root-Fenster durchsucht. Als letzter Fallback
  wird nach ``WM_CLASS`` gesucht.
- **Windows**: Das Zielfenster wird per WinAPI (``EnumWindows`` /
  ``GetWindowThreadProcessId``) gefunden. Anders als unter X11 reicht
  ``QWindow.fromWinId()``/``createWindowContainer()`` bei echten,
  fremdprozess-eigenen Fenstern (wie GTKWave) unter Windows haeufig NICHT
  aus, um eine sichtbare Einbettung zu erzielen (das Fenster bleibt als
  eigenstaendiges Top-Level-Fenster sichtbar, obwohl kein Fehler
  gemeldet wird). Stattdessen wird das Fenster direkt per WinAPI
  (``SetParent`` + Fensterstil-Anpassung) in ein natives Qt-Widget
  eingebettet und dessen Groesse per Event-Filter mit dem Container
  synchron gehalten.
- **macOS und alle anderen Faelle**: natives Window-Reparenting wird nicht
  unterstuetzt; GTKWave laeuft dann als eigenstaendiges Fenster weiter.

Schlaegt die Einbettung fehl (GTKWave nicht installiert, Timeout beim
Suchen des Fensters, nicht unterstuetzte Plattform, fehlendes
``python-xlib`` unter Linux), wird dies ueber das ``failed``-Signal mit
einer moeglichst konkreten Begruendung kommuniziert, sodass die
aufrufende GUI auf einen alternativen Wellenform-Viewer zurueckfallen
und dem Nutzer einen erneuten Versuch anbieten kann.
"""

from __future__ import annotations

import os
import shutil
import sys

from PySide6.QtCore import QEvent, QObject, QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QWidget

_POLL_INTERVAL_MS = 300
_MAX_POLL_ATTEMPTS = 60  # ~18 Sekunden Timeout - WSLg/langsamere Compositor koennen etwas brauchen
_GTKWAVE_WM_CLASS_HINTS = ("gtkwave",)
_MIN_SIGNIFICANT_WINDOW_SIZE = 100  # Pixel, zur Vermeidung falscher WM_CLASS-Treffer auf Hilfsfenster


def find_gtkwave_executable() -> str | None:
    """Sucht die gtkwave-Executable im PATH und gibt den vollen Pfad zurueck."""
    return shutil.which("gtkwave")


def is_embedding_supported() -> bool:
    """Ob fuer die aktuelle Plattform ueberhaupt ein Embedding-Verfahren existiert."""
    return sys.platform.startswith("linux") or sys.platform.startswith("win")


def is_xlib_available() -> bool:
    """Ob das optionale Paket ``python-xlib`` importierbar ist (nur Linux relevant)."""
    import importlib.util

    return importlib.util.find_spec("Xlib") is not None


def _collect_descendant_pids(root_pid: int) -> set[int]:
    """Sammelt ``root_pid`` und alle (rekursiven) Kindprozess-PIDs.

    Notwendig, da manche gtkwave-Pakete ueber ein Wrapper-Skript gestartet
    werden, das den eigentlichen GTK-Prozess per ``fork()`` als Kindprozess
    erzeugt statt sich per ``exec()`` selbst zu ersetzen. In diesem Fall
    stimmt die von ``QProcess`` gemeldete PID nicht mit der PID des
    tatsaechlichen Fensters ueberein.
    """
    pids = {root_pid}
    try:
        children_by_ppid: dict[int, list[int]] = {}
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat", encoding="utf-8", errors="replace") as stat_file:
                    stat = stat_file.read()
                # Format: "<pid> (<comm>) <state> <ppid> ...". comm kann
                # Leerzeichen/Klammern enthalten, daher ab der letzten ")" parsen.
                fields = stat[stat.rfind(")") + 2 :].split()
                ppid = int(fields[1])
                children_by_ppid.setdefault(ppid, []).append(int(entry))
            except (OSError, ValueError, IndexError):
                continue

        frontier = [root_pid]
        while frontier:
            current = frontier.pop()
            for child in children_by_ppid.get(current, []):
                if child not in pids:
                    pids.add(child)
                    frontier.append(child)
    except OSError:
        pass
    return pids


def _iter_x11_window_tree(root_window):
    """Traversiert rekursiv den kompletten X11-Fensterbaum ab ``root_window``
    (nicht nur die Top-Level-Fenster aus ``_NET_CLIENT_LIST``), da manche
    Compositor/Fenstermanager (z. B. unter WSLg) diese EWMH-Property nicht
    zuverlaessig pflegen und sie dadurch leer oder unvollstaendig bleibt."""
    stack = [root_window]
    while stack:
        current = stack.pop()
        yield current
        try:
            stack.extend(current.query_tree().children)
        except Exception:  # noqa: BLE001 - einzelne kaputte Fenster ueberspringen
            continue


def _scan_x11_windows(windows, net_wm_pid_atom, candidate_pids):
    """Durchsucht ``windows`` nach einem Treffer per PID (bevorzugt) oder
    ``WM_CLASS`` (Fallback). Gibt ``(pid_treffer, wm_class_treffer)``
    zurueck, wobei jeweils ``None`` moeglich ist."""
    from Xlib import X, Xatom
    from Xlib.error import XError

    wm_class_match = None
    for window in windows:
        try:
            prop = window.get_full_property(net_wm_pid_atom, X.AnyPropertyType)
            if prop and prop.value and int(prop.value[0]) in candidate_pids:
                return int(window.id), wm_class_match
            if wm_class_match is None:
                wm_class_prop = window.get_full_property(Xatom.WM_CLASS, X.AnyPropertyType)
                if wm_class_prop and wm_class_prop.value:
                    raw = wm_class_prop.value
                    text = raw.decode("latin-1", errors="ignore") if isinstance(raw, bytes) else str(raw)
                    if any(hint in text.lower() for hint in _GTKWAVE_WM_CLASS_HINTS) and _is_significant_x11_window(
                        window
                    ):
                        wm_class_match = int(window.id)
        except XError:
            continue
    return None, wm_class_match


def _is_significant_x11_window(window) -> bool:
    """Filtert kleine Hilfs-/Tooltip-Fenster aus dem WM_CLASS-Fallback aus."""
    from Xlib import X

    try:
        if window.get_attributes().map_state != X.IsViewable:
            return False
        geom = window.get_geometry()
        return geom.width >= _MIN_SIGNIFICANT_WINDOW_SIZE and geom.height >= _MIN_SIGNIFICANT_WINDOW_SIZE
    except Exception:  # noqa: BLE001
        return False


def _find_window_id_for_pid_x11(pid: int):
    """Einmaliger (nicht-blockierender) Versuch, das Top-Level-Fenster eines
    Prozesses (oder eines seiner Kindprozesse) unter X11 zu finden.

    Reihenfolge der Strategien:

    1. Schneller Pfad ueber die EWMH-Property ``_NET_CLIENT_LIST`` (Treffer
       per ``_NET_WM_PID`` oder als Fallback ``WM_CLASS``).
    2. Vollstaendiger Fensterbaum-Durchlauf ab dem Root-Fenster, falls (1)
       keinen Treffer liefert - robust auch dann, wenn der Fenstermanager/
       Compositor (z. B. unter WSLg) ``_NET_CLIENT_LIST`` nicht oder nur
       unvollstaendig pflegt.

    Gibt ``None`` zurueck, falls ``python-xlib`` fehlt, keine
    X11-Verbindung moeglich ist oder das Fenster (noch) nicht gefunden
    wurde.
    """
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
        net_wm_pid = conn.intern_atom("_NET_WM_PID")
        candidate_pids = _collect_descendant_pids(pid)

        net_client_list = conn.intern_atom("_NET_CLIENT_LIST")
        client_list = root.get_full_property(net_client_list, X.AnyPropertyType)
        top_level_windows = []
        if client_list and client_list.value:
            for win_id in client_list.value:
                try:
                    top_level_windows.append(conn.create_resource_object("window", win_id))
                except XError:
                    continue

        pid_match, wm_class_match = _scan_x11_windows(top_level_windows, net_wm_pid, candidate_pids)
        if pid_match is not None:
            return pid_match

        tree_pid_match, tree_wm_class_match = _scan_x11_windows(
            _iter_x11_window_tree(root), net_wm_pid, candidate_pids
        )
        if tree_pid_match is not None:
            return tree_pid_match

        return wm_class_match if wm_class_match is not None else tree_wm_class_match
    except Exception:  # noqa: BLE001 - robust gegenueber jeglichen X11-Fehlern
        return None
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


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


class _Win32ChildResizeSync(QObject):
    """Haelt die Groesse eines per ``SetParent()`` eingebetteten
    Win32-Kindfensters synchron mit der Groesse des Qt-Containers.

    Qt uebernimmt die Groessenanpassung fuer ein manuell (per WinAPI statt
    ueber Qt's eigene Fenstermechanik) reparentetes Fremdfenster nicht
    automatisch, daher wird hier auf Resize-/Show-Events des Containers
    reagiert und das Kindfenster per ``MoveWindow`` angepasst.
    """

    def __init__(self, hwnd: int, container: QWidget) -> None:
        super().__init__(container)
        self._hwnd = hwnd
        self._container = container

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if watched is self._container and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._resize_child()
        return False

    def _resize_child(self) -> None:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        width = max(self._container.width(), 1)
        height = max(self._container.height(), 1)
        user32.MoveWindow(self._hwnd, 0, 0, width, height, True)


def _embed_foreign_window_windows(hwnd: int, container: QWidget) -> None:
    """Bettet das Win32-Fenster ``hwnd`` per ``SetParent()`` direkt in
    ``container`` ein und passt Fensterstil sowie Groesse an.

    ``QWindow.fromWinId()`` kombiniert mit ``createWindowContainer()``
    meldet zwar keinen Fehler, bettet ein echtes, fremdprozess-eigenes
    Fenster (wie GTKWave) unter Windows aber oft nicht sichtbar ein - das
    Fenster bleibt als eigenstaendiges Top-Level-Fenster sichtbar. Der
    direkte WinAPI-Weg (``SetParent`` + Stiländerung) ist zuverlässiger.
    """
    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]

    gwl_style = -16
    gwl_exstyle = -20
    ws_child = 0x40000000
    ws_visible = 0x10000000
    ws_popup = 0x80000000
    ws_caption = 0x00C00000
    ws_thickframe = 0x00040000
    ws_sysmenu = 0x00080000
    ws_minimizebox = 0x00020000
    ws_maximizebox = 0x00010000
    ws_ex_dlgmodalframe = 0x00000001
    ws_ex_windowedge = 0x00000100
    ws_ex_clientedge = 0x00000200
    ws_ex_appwindow = 0x00040000
    swp_framechanged = 0x0020
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010
    swp_showwindow = 0x0040

    ctypes.windll.kernel32.SetLastError(0)  # type: ignore[attr-defined]

    if not user32.IsWindow(hwnd):
        raise OSError(f"Fenster-Handle {hwnd} ist ungueltig (Fenster bereits geschlossen?).")

    container_hwnd = int(container.winId())
    if not container_hwnd:
        raise OSError("Qt-Container besitzt kein natives Fenster-Handle.")

    style = user32.GetWindowLongW(hwnd, gwl_style)
    style &= ~(ws_popup | ws_caption | ws_thickframe | ws_sysmenu | ws_minimizebox | ws_maximizebox)
    style |= ws_child | ws_visible
    user32.SetWindowLongW(hwnd, gwl_style, style)

    ex_style = user32.GetWindowLongW(hwnd, gwl_exstyle)
    ex_style &= ~(ws_ex_dlgmodalframe | ws_ex_windowedge | ws_ex_clientedge | ws_ex_appwindow)
    user32.SetWindowLongW(hwnd, gwl_exstyle, ex_style)

    previous_parent = user32.SetParent(hwnd, container_hwnd)
    if not previous_parent:
        raise ctypes.WinError()  # type: ignore[attr-defined]

    user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        max(container.width(), 1),
        max(container.height(), 1),
        swp_framechanged | swp_nozorder | swp_noactivate | swp_showwindow,
    )

    resizer = _Win32ChildResizeSync(hwnd, container)
    container.installEventFilter(resizer)
    # Referenz halten, damit der Resizer nicht vorzeitig vom GC entfernt wird.
    container._ghdl_studio_resize_sync = resizer  # type: ignore[attr-defined]


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
            self.failed.emit(self._build_timeout_reason())

    def _build_timeout_reason(self) -> str:
        reason = "GTKWave-Fenster wurde nicht rechtzeitig gefunden (Timeout)."
        if sys.platform.startswith("linux"):
            if not is_xlib_available():
                reason += (
                    " Das Paket 'python-xlib' ist in dieser Python-Umgebung nicht installiert "
                    "(z. B. mit 'pip install -r requirements.txt' im aktivierten venv nachinstallieren)."
                )
            else:
                reason += (
                    " 'python-xlib' ist installiert, das Fenster wurde aber trotzdem nicht "
                    "gefunden - moeglicherweise ist der Fenstermanager/Compositor "
                    "(z. B. unter WSLg) zu langsam. Versuche es ggf. per Klick auf "
                    "'Erneut versuchen' noch einmal."
                )
        return reason

    def _finish_embedding(self, win_id: int) -> None:
        if sys.platform.startswith("win"):
            # Unter Windows wird zunaechst ein leerer, natives Qt-Widget
            # als Container erzeugt und sofort eingehaengt (damit Layout
            # und Groesse korrekt gesetzt werden), das eigentliche
            # SetParent() erfolgt erst danach ueber einen 0ms-Timer, wenn
            # der Container bereits eine belastbare Groesse hat.
            container = QWidget()
            container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            self.embedded.emit(container)
            QTimer.singleShot(0, lambda: self._finish_embedding_windows(win_id, container))
            return

        foreign_window = QWindow.fromWinId(win_id)
        if foreign_window is None:
            self.failed.emit("GTKWave-Fenster konnte nicht als Qt-Fenster referenziert werden.")
            return
        container = QWidget.createWindowContainer(foreign_window, self._parent_widget)
        self.embedded.emit(container)

    def _finish_embedding_windows(self, hwnd: int, container: QWidget) -> None:
        try:
            _embed_foreign_window_windows(hwnd, container)
        except Exception as exc:  # noqa: BLE001 - dem Nutzer die Ursache anzeigen
            self.failed.emit(f"GTKWave-Fenster konnte nicht eingebettet werden: {exc}")
