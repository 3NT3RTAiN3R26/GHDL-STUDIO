"""Einstiegspunkt der Anwendung."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from ghdl_studio import __version__
from ghdl_studio.branding import apply_application_icon
from ghdl_studio.main_window import MainWindow
from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM
from ghdl_studio.settings import AppSettings
from ghdl_studio.surfer_embed import ensure_linux_xcb_platform
from ghdl_studio.theme import apply_dark_theme
from ghdl_studio.widgets.startup_mode_dialog import StartupModeDialog


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI for ``ghdl-studio`` (``--version`` before the GUI starts)."""
    parser = argparse.ArgumentParser(
        prog="ghdl-studio",
        description="Cross-platform graphical interface for GHDL (VHDL simulator).",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"ghdl-studio {__version__}",
        help="Show program version and exit",
    )
    return parser


def _enable_stdio_for_frozen_cli(argv: list[str]) -> None:
    """Attach stdio for ``--version`` / ``--help`` on frozen Windows builds.

    Windowed (``console=False``) PyInstaller binaries often leave ``sys.stdout``
    disconnected; without this, ``GHDL-Studio.exe --version`` prints nothing.
    Prefer inherited pipes (CI redirection), then attach/allocate a console.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if not any(arg in {"-V", "--version", "-h", "--help"} for arg in argv):
        return

    def _reopen_fd(name: str, fd: int, mode: str) -> bool:
        try:
            setattr(
                sys,
                name,
                open(fd, mode, encoding="utf-8", errors="replace", closefd=False),
            )
            return True
        except OSError:
            return False

    if _reopen_fd("stdout", 1, "w") and _reopen_fd("stderr", 2, "w"):
        _reopen_fd("stdin", 0, "r")
        return

    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # ATTACH_PARENT_PROCESS = -1 (interactive cmd.exe).
        if not kernel32.AttachConsole(-1):
            kernel32.AllocConsole()
    except Exception:  # noqa: BLE001 - best-effort CLI only
        pass

    for name, con, mode in (
        ("stdin", "CONIN$", "r"),
        ("stdout", "CONOUT$", "w"),
        ("stderr", "CONOUT$", "w"),
    ):
        try:
            setattr(sys, name, open(con, mode, encoding="utf-8", errors="replace"))
        except OSError:
            if name != "stdin" and getattr(sys, name, None) is None:
                setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _resolve_session(settings: AppSettings) -> tuple[str, str, str] | None:
    """Return ``(mode, pro_path, project_path)`` or ``None`` if cancelled.

    ``project_path`` is set when the user opens a recent ``.ghdlstudio`` file
    from the startup dialog.
    """
    # QSettings may return 0/1 or "true"/"false" depending on platform.
    if bool(settings.remember_startup_mode):
        mode = settings.startup_mode
        if mode == MODE_OSVVM:
            pro = (settings.last_pro_file or "").strip()
            if pro and Path(pro).expanduser().is_file():
                return MODE_OSVVM, str(Path(pro).expanduser().resolve()), ""
            # Remembered OSVVM without a valid .pro — fall through to dialog.
        elif mode == MODE_NORMAL:
            return MODE_NORMAL, "", ""

    dialog = StartupModeDialog(settings)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    dialog.apply_to_settings()
    if dialog.selected_project_path:
        return MODE_NORMAL, "", dialog.selected_project_path
    if dialog.selected_mode == MODE_OSVVM:
        pro = dialog.selected_pro_file.strip()
        return MODE_OSVVM, str(Path(pro).expanduser().resolve()), ""
    return MODE_NORMAL, "", ""


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``ghdl-studio`` console script."""
    cli_argv = list(sys.argv[1:] if argv is None else argv)
    _enable_stdio_for_frozen_cli(cli_argv)
    parser = build_arg_parser()
    # ``--version`` / ``-V`` exit here via ArgumentParser action.
    _, remaining = parser.parse_known_args(cli_argv)
    if argv is None:
        # Do not forward consumed flags to Qt.
        sys.argv = [sys.argv[0], *remaining]

    # Vor QApplication: unter Linux/WSL XCB bevorzugen (wenn libxcb-cursor
    # vorhanden), damit Surfer per X11-Reparenting eingebettet werden kann.
    ensure_linux_xcb_platform()
    # Required by Qt WebEngine when embedding OSVVM HTML reports.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        # Import WebEngine before QApplication when available (Chromium init).
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        except ImportError:
            pass
        app = QApplication(sys.argv)
    except Exception as exc:  # noqa: BLE001 - Qt kann hier auch hart abbrechen
        print(f"GHDL Studio could not start: {exc}", file=sys.stderr)
        if sys.platform.startswith("linux"):
            print(
                "Tip (Ubuntu/Debian/WSL): sudo apt install libxcb-cursor0\n"
                "Then start again. Alternatively: export QT_QPA_PLATFORM=wayland",
                file=sys.stderr,
            )
        return 1
    app.setApplicationName("GHDL Studio")
    app.setApplicationVersion(__version__)
    apply_application_icon(app)
    apply_dark_theme(app)

    settings = AppSettings()
    session = _resolve_session(settings)
    if session is None:
        return 0
    mode, pro_path, project_path = session

    if mode == MODE_OSVVM and not pro_path and not project_path:
        QMessageBox.warning(
            None,
            "No .pro file",
            "OSVVM mode requires a .pro file. Please choose one at startup "
            "or via File → Open .pro…",
        )
        return 1

    window = MainWindow(mode=mode, pro_path=pro_path or None)
    window.show()
    if project_path:
        window.open_studio_project_path(project_path)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
