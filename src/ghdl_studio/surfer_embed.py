"""Einbettung von Surfer (https://surfer-project.org/) als natives Fenster.

Surfer ist ein moderner Wellenform-Viewer (VCD/FST/GHW) und bietet keine
offizielle Embedding-API. Dieses Modul realisiert die Einbettung ueber
plattformspezifisches "Window Reparenting":

- **Linux/X11**: Surfer wird als Subprozess gestartet, anschliessend wird
  dessen Top-Level-Fenster gefunden (benoetigt ``python-xlib``) und per
  X11-``XReparentWindow`` in ein natives Qt-Container-Widget gehaengt
  (analog zu ``SetParent`` unter Windows). Die Fenstersuche versucht
  zuerst ``_NET_CLIENT_LIST`` (PID / Kind-PIDs), dann den kompletten
  X11-Fensterbaum, zuletzt ``WM_CLASS``.
  ``QWindow.fromWinId()`` wird bewusst *nicht* verwendet: Unter WSL/WSLg
  und generell mit dem Qt-Wayland-Plugin schlaegt das mit
  ``platform plugin does not support foreign windows`` fehl. Deshalb
  startet die Anwendung unter Linux mit X11/XWayland bevorzugt das
  ``xcb``-Plugin (siehe ``ensure_linux_xcb_platform``).
- **Windows**: Fenstersuche per WinAPI; Einbettung per ``SetParent`` +
  Stil-/Groessen-Sync (nicht ``QWindow.fromWinId``).
- **macOS und alle anderen Faelle**: kein natives Reparenting; Surfer
  laeuft als eigenstaendiges Fenster weiter.

Schlaegt die Einbettung fehl, signalisiert ``failed`` eine konkrete
Begruendung; die GUI faellt auf den internen Wellenform-Viewer zurueck.
"""

from __future__ import annotations

import os
import shutil
import sys

from PySide6.QtCore import QEvent, QObject, QProcess, Qt, QTimer, Signal
from PySide6.QtWidgets import QWidget

_POLL_INTERVAL_MS = 300
_MAX_POLL_ATTEMPTS = 60  # ~18 Sekunden Timeout - WSLg/langsamere Compositor koennen etwas brauchen
_SURFER_WM_CLASS_HINTS = ("surfer",)
_MIN_SIGNIFICANT_WINDOW_SIZE = 100  # Pixel, zur Vermeidung falscher WM_CLASS-Treffer auf Hilfsfenster


def find_surfer_executable() -> str | None:
    """Sucht die surfer-Executable im PATH und gibt den vollen Pfad zurueck."""
    return shutil.which("surfer")


def is_embedding_supported() -> bool:
    """Ob fuer die aktuelle Plattform ueberhaupt ein Embedding-Verfahren existiert."""
    return sys.platform.startswith("linux") or sys.platform.startswith("win")


def is_xlib_available() -> bool:
    """Ob das optionale Paket ``python-xlib`` importierbar ist (nur Linux relevant)."""
    import importlib.util

    return importlib.util.find_spec("Xlib") is not None


def is_xcb_cursor_available() -> bool:
    """Ob ``libxcb-cursor`` geladen werden kann (ab Qt 6.5 Pflicht fuer xcb).

    Fehlt das Paket (Ubuntu/Debian: ``libxcb-cursor0``), bricht Qt beim
    Laden des xcb-Plugins mit
    ``From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed…`` ab.
    """
    if not sys.platform.startswith("linux"):
        return False
    try:
        import ctypes.util

        # Verschiedene Distros liefern den Soname als libxcb-cursor.so.0
        # bzw. finden ihn ueber find_library("xcb-cursor").
        if ctypes.util.find_library("xcb-cursor"):
            return True
        ctypes.CDLL("libxcb-cursor.so.0")
        return True
    except OSError:
        return False


def ensure_linux_xcb_platform() -> None:
    """Waehlt ein sicheres Qt-Platform-Plugin unter Linux *vor* ``QApplication``.

    - Mit ``libxcb-cursor`` und ``DISPLAY``: ``xcb`` (noetig fuer Surfer-
      Einbettung per X11-Reparenting; unter WSLg oft sonst Wayland).
    - Ohne ``libxcb-cursor``: Qt 6.5+ bricht bei xcb hart ab. Deshalb wird
      bei vorhandenem ``WAYLAND_DISPLAY`` explizit ``wayland`` gesetzt —
      auch wenn ``QT_QPA_PLATFORM=xcb`` bereits in der Umgebung steht.
      Nur so startet die GUI unter WSL/Ubuntu ohne das Paket; Surfer laeuft
      dann extern bzw. der interne Viewer greift.
    """
    if not sys.platform.startswith("linux"):
        return

    existing = (os.environ.get("QT_QPA_PLATFORM") or "").strip()
    has_display = bool(os.environ.get("DISPLAY"))
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    cursor_ok = is_xcb_cursor_available()

    if cursor_ok:
        if existing:
            return
        if has_display:
            os.environ["QT_QPA_PLATFORM"] = "xcb"
        return

    # libxcb-cursor fehlt → xcb ist toedlich. Wayland erzwingen, falls moeglich.
    apt_hint = "sudo apt install libxcb-cursor0"
    if has_wayland:
        if existing and existing != "wayland":
            print(
                f"Hinweis: QT_QPA_PLATFORM={existing} wird durch 'wayland' ersetzt, "
                f"weil libxcb-cursor fehlt (sonst Absturz). Fuer Surfer-Einbettung: {apt_hint}",
                file=sys.stderr,
            )
        elif not existing:
            print(
                "Hinweis: libxcb-cursor fehlt — starte mit QT_QPA_PLATFORM=wayland. "
                f"Fuer Surfer-Einbettung wie unter Windows: {apt_hint}",
                file=sys.stderr,
            )
        os.environ["QT_QPA_PLATFORM"] = "wayland"
        return

    if existing == "xcb" or (not existing and has_display):
        print(
            "Fehler: libxcb-cursor fehlt; das Qt-xcb-Plugin kann nicht geladen werden.\n"
            f"Bitte installieren: {apt_hint}\n"
            "Danach GHDL Studio neu starten.",
            file=sys.stderr,
        )
        # xcb aus der Umgebung nehmen, damit ein spaeterer manueller
        # Wayland-Start nicht weiter blockiert wird.
        if existing == "xcb":
            del os.environ["QT_QPA_PLATFORM"]


def qt_platform_name() -> str:
    """Aktueller Qt-Platform-Plugin-Name (``xcb``, ``wayland``, …), oder leer."""
    try:
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            return ""
        return str(app.platformName())
    except Exception:  # noqa: BLE001
        return ""


def _collect_descendant_pids(root_pid: int) -> set[int]:
    """Sammelt ``root_pid`` und alle (rekursiven) Kindprozess-PIDs.

    Notwendig, da manche surfer-Pakete ueber ein Wrapper-Skript gestartet
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
                    if any(hint in text.lower() for hint in _SURFER_WM_CLASS_HINTS) and _is_significant_x11_window(
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


class _X11ChildResizeSync(QObject):
    """Haelt die Groesse eines per ``XReparentWindow`` eingebetteten
    X11-Kindfensters synchron mit dem Qt-Container."""

    def __init__(self, xid: int, container: QWidget) -> None:
        super().__init__(container)
        self._xid = xid
        self._container = container
        from Xlib import display  # noqa: PLC0415 - optionale Abhaengigkeit

        self._display = display.Display()
        self._child = self._display.create_resource_object("window", xid)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if watched is self._container and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._resize_child()
        return False

    def _resize_child(self) -> None:
        try:
            width = max(self._container.width(), 1)
            height = max(self._container.height(), 1)
            self._child.configure(width=width, height=height)
            self._display.sync()
        except Exception:  # noqa: BLE001 - Resize-Fehler nicht eskalieren
            pass

    def close_display(self) -> None:
        try:
            self._display.close()
        except Exception:  # noqa: BLE001
            pass


def _embed_foreign_window_x11(xid: int, container: QWidget) -> None:
    """Bettet das X11-Fenster ``xid`` per ``XReparentWindow`` in ``container`` ein.

    Im Gegensatz zu ``QWindow.fromWinId()``/``createWindowContainer()``
    funktioniert dieser Weg auch dann, wenn das Qt-Platform-Plugin keine
    "foreign windows" unterstuetzt — solange Qt selbst ueber XCB laeuft und
    ``container.winId()`` eine echte X11-Window-ID liefert (WSLg via XWayland).
    """
    from Xlib import X, display  # noqa: PLC0415
    from Xlib.error import XError

    platform = qt_platform_name()
    if platform and platform != "xcb":
        raise OSError(
            f"Qt laeuft mit dem Platform-Plugin '{platform}', nicht 'xcb'. "
            "X11-Einbettung von Surfer erfordert XCB (unter WSL/WSLg: App neu "
            "starten — GHDL Studio setzt QT_QPA_PLATFORM=xcb automatisch, sofern "
            "nicht anders gesetzt; alternativ manuell "
            "'export QT_QPA_PLATFORM=xcb' vor dem Start)."
        )

    container_xid = int(container.winId())
    if not container_xid:
        raise OSError("Qt-Container besitzt keine X11-Window-ID (winId=0).")

    conn = display.Display()
    try:
        child = conn.create_resource_object("window", xid)
        parent = conn.create_resource_object("window", container_xid)
        try:
            # Vom Window-Manager loesen, dann als Child in den Qt-Container.
            child.unmap()
            conn.sync()
            child.reparent(parent, 0, 0)
            child.configure(
                width=max(container.width(), 1),
                height=max(container.height(), 1),
                border_width=0,
            )
            child.map()
            conn.sync()
            # Sichtbarkeit / Map-State kurz verifizieren
            attrs = child.get_attributes()
            if attrs.map_state == X.IsUnmapped:
                child.map()
                conn.sync()
        except XError as exc:
            raise OSError(f"XReparentWindow fehlgeschlagen: {exc}") from exc
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

    resizer = _X11ChildResizeSync(xid, container)
    container.installEventFilter(resizer)
    container._ghdl_studio_resize_sync = resizer  # type: ignore[attr-defined]
    # Sofort einmal auf aktuelle Container-Groesse bringen
    resizer._resize_child()


def _to_win32_long(value: int) -> int:
    """Normiert einen Python-Int auf den Wertebereich von Win32 ``LONG``
    (signed 32-bit).

    Bitweise Operationen auf Fensterstilen (z. B. ``style &= ~WS_POPUP``)
    erzeugen in Python 3 leicht Werte ausserhalb von ``[-2^31, 2^31)``,
    obwohl die unteren 32 Bit korrekt sind. ``ctypes`` unter Windows lehnt
    solche Werte beim Aufruf von ``SetWindowLongW`` dann mit
    ``OverflowError: int too long to convert`` (typischerweise an
    Argument 3) ab.
    """
    unsigned_32 = int(value) & 0xFFFFFFFF
    return unsigned_32 - 0x100000000 if unsigned_32 >= 0x80000000 else unsigned_32


def _configure_user32_winapi(user32) -> None:
    """Setzt ``argtypes``/``restype`` fuer die genutzten user32-Funktionen,
    damit 64-bit-``HWND``-Werte und 32-bit-``LONG``-Stile korrekt
    konvertiert werden (ohne ``argtypes`` nimmt ``ctypes.windll`` fuer
    Integer standardmaessig ``c_int``, was bei grossen Handles oder
    falsch normierten Stilen zu ``OverflowError`` fuehrt)."""
    import ctypes
    from ctypes import wintypes

    if getattr(user32, "_ghdl_studio_configured", False):
        return

    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, wintypes.LPDWORD]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.MoveWindow.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.BOOL,
    ]
    user32.MoveWindow.restype = wintypes.BOOL
    user32._ghdl_studio_configured = True  # type: ignore[attr-defined]


def _find_hwnd_for_pid_windows(pid: int):
    """Einmaliger Versuch, das sichtbare Top-Level-Fenster eines Prozesses
    unter Windows per WinAPI zu finden."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    _configure_user32_winapi(user32)
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
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
        _configure_user32_winapi(user32)
        width = max(self._container.width(), 1)
        height = max(self._container.height(), 1)
        user32.MoveWindow(self._hwnd, 0, 0, width, height, True)


def _embed_foreign_window_windows(hwnd: int, container: QWidget) -> None:
    """Bettet das Win32-Fenster ``hwnd`` per ``SetParent()`` direkt in
    ``container`` ein und passt Fensterstil sowie Groesse an.

    ``QWindow.fromWinId()`` kombiniert mit ``createWindowContainer()``
    meldet zwar keinen Fehler, bettet ein echtes, fremdprozess-eigenes
    Fenster (wie Surfer) unter Windows aber oft nicht sichtbar ein - das
    Fenster bleibt als eigenstaendiges Top-Level-Fenster sichtbar. Der
    direkte WinAPI-Weg (``SetParent`` + Stiländerung) ist zuverlässiger.
    """
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    _configure_user32_winapi(user32)

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

    # Fensterstile immer ueber unsigned-32-Bit-Arithmetik berechnen und erst
    # danach auf signed LONG normieren - sonst OverflowError unter Win64.
    style_bits = int(user32.GetWindowLongW(hwnd, gwl_style)) & 0xFFFFFFFF
    clear_bits = ws_popup | ws_caption | ws_thickframe | ws_sysmenu | ws_minimizebox | ws_maximizebox
    style_bits = (style_bits & ~clear_bits & 0xFFFFFFFF) | ws_child | ws_visible
    user32.SetWindowLongW(hwnd, gwl_style, _to_win32_long(style_bits))

    ex_bits = int(user32.GetWindowLongW(hwnd, gwl_exstyle)) & 0xFFFFFFFF
    ex_clear = ws_ex_dlgmodalframe | ws_ex_windowedge | ws_ex_clientedge | ws_ex_appwindow
    ex_bits = ex_bits & ~ex_clear & 0xFFFFFFFF
    user32.SetWindowLongW(hwnd, gwl_exstyle, _to_win32_long(ex_bits))

    previous_parent = user32.SetParent(hwnd, container_hwnd)
    if not previous_parent:
        raise ctypes.WinError()  # type: ignore[attr-defined]

    user32.SetWindowPos(
        hwnd,
        wintypes.HWND(0),
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


class SurferEmbedder(QObject):
    """Startet Surfer fuer eine VCD-Datei und bettet dessen Fenster ein.

    Verwendung::

        embedder = SurferEmbedder(parent)
        embedder.embedded.connect(on_embedded)   # erhaelt das Container-QWidget
        embedder.failed.connect(on_failed)        # erhaelt eine Fehlermeldung
        embedder.start(surfer_path, vcd_path, parent_widget)
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
        proc = self._process
        self._process = None
        if proc is not None:
            if proc.state() != QProcess.ProcessState.NotRunning:
                proc.kill()
                proc.waitForFinished(3000)
            proc.deleteLater()

    def start(self, surfer_executable: str, vcd_path: str, parent_widget: QWidget) -> None:
        """Startet Surfer fuer ``vcd_path`` und versucht anschliessend, das
        entstehende Fenster in ``parent_widget`` einzubetten. Ergebnis wird
        ueber ``embedded``/``failed`` signalisiert."""
        self.stop()

        if not is_embedding_supported():
            self.failed.emit(
                "Fenster-Einbettung wird auf dieser Plattform nicht unterstuetzt "
                "(nur Linux/X11 und Windows). Surfer wird als eigenstaendiges "
                "Fenster geoeffnet."
            )
            self._launch_standalone(surfer_executable, vcd_path)
            return

        self._parent_widget = parent_widget
        self._attempts = 0
        self._process = QProcess(self)
        self._process.start(surfer_executable, [vcd_path])
        if not self._process.waitForStarted(5000):
            self.failed.emit("Surfer konnte nicht gestartet werden. Ist Surfer installiert und im PATH?")
            self._process = None
            return

        self._timer.start()

    def _launch_standalone(self, surfer_executable: str, vcd_path: str) -> None:
        QProcess.startDetached(surfer_executable, [vcd_path])

    def _poll_for_window(self) -> None:
        if self._process is None or not self.is_running():
            self._timer.stop()
            self.failed.emit("Surfer wurde beendet, bevor ein Fenster eingebettet werden konnte.")
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
        reason = "Surfer-Fenster wurde nicht rechtzeitig gefunden (Timeout)."
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
        # Windows und Linux nutzen denselben Ablauf: zuerst einen nativen
        # Qt-Container ins Layout haengen (winId + Groesse), dann im
        # naechsten Event-Loop-Tick per OS-API reparenten. ``embedded``
        # wird erst nach erfolgreichem Reparent gesendet.
        if sys.platform.startswith("win") or sys.platform.startswith("linux"):
            container = QWidget(self._parent_widget)
            container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
            parent = self._parent_widget
            if parent is not None and parent.layout() is not None:
                parent.layout().addWidget(container)
            container.show()
            if sys.platform.startswith("win"):
                QTimer.singleShot(0, lambda: self._complete_os_embed(win_id, container, "windows"))
            else:
                QTimer.singleShot(0, lambda: self._complete_os_embed(win_id, container, "x11"))
            return

        self.failed.emit("Fenster-Einbettung wird auf dieser Plattform nicht unterstuetzt.")

    def _complete_os_embed(self, win_id: int, container: QWidget, backend: str) -> None:
        try:
            if backend == "windows":
                _embed_foreign_window_windows(win_id, container)
            else:
                _embed_foreign_window_x11(win_id, container)
        except Exception as exc:  # noqa: BLE001 - dem Nutzer die Ursache anzeigen
            parent = container.parentWidget()
            if parent is not None and parent.layout() is not None:
                parent.layout().removeWidget(container)
            container.hide()
            resizer = getattr(container, "_ghdl_studio_resize_sync", None)
            if resizer is not None and hasattr(resizer, "close_display"):
                resizer.close_display()
            container.deleteLater()
            self.failed.emit(f"Surfer-Fenster konnte nicht eingebettet werden: {exc}")
            return
        self.embedded.emit(container)
