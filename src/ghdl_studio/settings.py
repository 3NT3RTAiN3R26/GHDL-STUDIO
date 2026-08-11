"""Persistente Anwendungseinstellungen ueber QSettings.

QSettings speichert plattformabhaengig (Registry unter Windows, plist unter
macOS, ini-Dateien unter Linux) und sorgt so dafuer, dass sich die GUI auf
allen unterstuetzten Plattformen gleich verhaelt.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    DEFAULT_STD,
    DEFAULT_WAVE_FORMAT,
    find_ghdl_executable,
    normalize_wave_format,
)
from ghdl_studio.osvvm_commands import (
    DEFAULT_OSVVM_HTML_REPORT,
    MODE_NORMAL,
    find_tclsh_executable,
)
from ghdl_studio.surfer_embed import find_surfer_executable
from ghdl_studio.tool_backend import (
    DEFAULT_TOOL_BACKEND,
    normalize_tool_backend,
)

ORG_NAME = "GhdlStudio"
APP_NAME = "GhdlStudio"


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings(ORG_NAME, APP_NAME)

    def _set(self, key: str, value: object) -> None:
        """Schreibt den Wert und synchronisiert sofort auf die Festplatte.

        QSettings synchronisiert normalerweise erst beim Zerstoeren des
        Objekts oder periodisch im Hintergrund. Bei kurzlebigen Prozessen
        (z. B. abruptem Beenden) kann das dazu fuehren, dass zuletzt
        gesetzte Werte verloren gehen. Der explizite sync()-Aufruf stellt
        sicher, dass Einstellungen sofort persistiert werden.
        """
        self._settings.setValue(key, value)
        self._settings.sync()

    @property
    def ghdl_executable(self) -> str:
        stored = self._settings.value("ghdl_executable", "", str)
        if stored:
            return stored
        return find_ghdl_executable() or ""

    @ghdl_executable.setter
    def ghdl_executable(self, value: str) -> None:
        self._set("ghdl_executable", value)

    @property
    def vhdl_std(self) -> str:
        return self._settings.value("vhdl_std", DEFAULT_STD, str)

    @vhdl_std.setter
    def vhdl_std(self, value: str) -> None:
        self._set("vhdl_std", value)

    @property
    def analyze_extra_args(self) -> list[str]:
        if not self._settings.contains("analyze_extra_args"):
            return list(DEFAULT_ANALYZE_EXTRA_ARGS)
        stored = self._settings.value("analyze_extra_args", "", str)
        return stored.split()

    @analyze_extra_args.setter
    def analyze_extra_args(self, value: list[str]) -> None:
        self._set("analyze_extra_args", " ".join(value))

    @property
    def elaborate_extra_args(self) -> list[str]:
        if not self._settings.contains("elaborate_extra_args"):
            return list(DEFAULT_ELABORATE_EXTRA_ARGS)
        stored = self._settings.value("elaborate_extra_args", "", str)
        return stored.split()

    @elaborate_extra_args.setter
    def elaborate_extra_args(self, value: list[str]) -> None:
        self._set("elaborate_extra_args", " ".join(value))

    @property
    def run_extra_args(self) -> list[str]:
        if not self._settings.contains("run_extra_args"):
            return list(DEFAULT_RUN_EXTRA_ARGS)
        stored = self._settings.value("run_extra_args", "", str)
        return stored.split()

    @run_extra_args.setter
    def run_extra_args(self, value: list[str]) -> None:
        self._set("run_extra_args", " ".join(value))

    @property
    def output_dir(self) -> str:
        return self._settings.value("output_dir", DEFAULT_OUTPUT_DIR, str) or DEFAULT_OUTPUT_DIR

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._set("output_dir", value)

    @property
    def osvvm_lib_path(self) -> str:
        return self._settings.value("osvvm_lib_path", "", str) or ""

    @osvvm_lib_path.setter
    def osvvm_lib_path(self, value: str) -> None:
        self._set("osvvm_lib_path", value)

    @property
    def osvvm_library_directory(self) -> str:
        """Root passed to OSVVM ``SetLibraryDirectory`` when precompiling."""
        return self._settings.value("osvvm_library_directory", "", str) or ""

    @osvvm_library_directory.setter
    def osvvm_library_directory(self, value: str) -> None:
        self._set("osvvm_library_directory", value)

    @property
    def custom_lib_path(self) -> str:
        return self._settings.value("custom_lib_path", "", str) or ""

    @custom_lib_path.setter
    def custom_lib_path(self, value: str) -> None:
        self._set("custom_lib_path", value)

    @property
    def surfer_executable(self) -> str:
        stored = self._settings.value("surfer_executable", "", str)
        if stored:
            return stored
        return find_surfer_executable() or ""

    @surfer_executable.setter
    def surfer_executable(self, value: str) -> None:
        self._set("surfer_executable", value)

    @property
    def surfer_integration_enabled(self) -> bool:
        return self._settings.value("surfer_integration_enabled", True, bool)

    @surfer_integration_enabled.setter
    def surfer_integration_enabled(self, value: bool) -> None:
        self._set("surfer_integration_enabled", value)

    @property
    def wave_format(self) -> str:
        """Preferred Normal-mode waveform dump: ``vcd``, ``ghw``, or ``both``."""
        stored = self._settings.value("wave_format", DEFAULT_WAVE_FORMAT, str)
        return normalize_wave_format(stored)

    @wave_format.setter
    def wave_format(self, value: str) -> None:
        self._set("wave_format", normalize_wave_format(value))

    @property
    def tool_backend(self) -> str:
        """``native`` or ``wsl`` — how GHDL/tclsh/Surfer are launched on Windows."""
        stored = self._settings.value("tool_backend", DEFAULT_TOOL_BACKEND, str)
        return normalize_tool_backend(stored)

    @tool_backend.setter
    def tool_backend(self, value: str) -> None:
        self._set("tool_backend", normalize_tool_backend(value))

    @property
    def last_project_dir(self) -> str:
        return self._settings.value("last_project_dir", "", str)

    @last_project_dir.setter
    def last_project_dir(self, value: str) -> None:
        self._set("last_project_dir", value)

    @property
    def recent_files(self) -> list[str]:
        return self._settings.value("recent_files", [], list) or []

    @recent_files.setter
    def recent_files(self, value: list[str]) -> None:
        self._set("recent_files", value)

    @property
    def recent_projects(self) -> list[str]:
        """Newest-first list of ``.ghdlstudio`` project paths (existing files only)."""
        raw = self._settings.value("recent_projects", [], list) or []
        result: list[str] = []
        seen: set[str] = set()
        for entry in raw:
            path = str(entry or "").strip()
            if not path or path in seen:
                continue
            expanded = Path(path).expanduser()
            if not expanded.is_file():
                continue
            try:
                resolved = str(expanded.resolve())
            except OSError:
                resolved = str(expanded)
            if resolved in seen:
                continue
            seen.add(path)
            seen.add(resolved)
            result.append(resolved)
        # Persist pruned list when stale entries were dropped.
        if len(result) != len([e for e in raw if str(e or "").strip()]):
            self._set("recent_projects", result)
        return result

    @recent_projects.setter
    def recent_projects(self, value: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for entry in value or []:
            path = str(entry or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            cleaned.append(path)
        self._set("recent_projects", cleaned[:20])

    def remember_project(self, path: str, *, limit: int = 10) -> None:
        """Push *path* to the front of :attr:`recent_projects`."""
        if not path:
            return
        try:
            resolved = str(Path(path).expanduser().resolve())
        except OSError:
            resolved = str(Path(path).expanduser())
        if not Path(resolved).is_file():
            return
        current = [p for p in self.recent_projects if p != resolved]
        self.recent_projects = [resolved, *current][: max(1, limit)]

    @property
    def startup_mode(self) -> str:
        """``normal`` (manual GHDL files) or ``osvvm`` (.pro via TCL)."""
        value = self._settings.value("startup_mode", MODE_NORMAL, str) or MODE_NORMAL
        return value if value in ("normal", "osvvm") else MODE_NORMAL

    @startup_mode.setter
    def startup_mode(self, value: str) -> None:
        self._set("startup_mode", value)

    @property
    def remember_startup_mode(self) -> bool:
        value = self._settings.value("remember_startup_mode", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return False

    @remember_startup_mode.setter
    def remember_startup_mode(self, value: bool) -> None:
        self._set("remember_startup_mode", bool(value))

    @property
    def last_pro_file(self) -> str:
        return self._settings.value("last_pro_file", "", str) or ""

    @last_pro_file.setter
    def last_pro_file(self, value: str) -> None:
        self._set("last_pro_file", value)

    @property
    def pro_files(self) -> list[str]:
        """Ordered list of OSVVM ``.pro`` paths shown in Project files."""
        raw = self._settings.value("pro_files", [], list) or []
        result: list[str] = []
        seen: set[str] = set()
        for entry in raw:
            path = str(entry or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            result.append(path)
        return result

    @pro_files.setter
    def pro_files(self, value: list[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for entry in value or []:
            path = str(entry or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            cleaned.append(path)
        self._set("pro_files", cleaned)

    @property
    def tcl_executable(self) -> str:
        stored = self._settings.value("tcl_executable", "", str)
        if stored:
            return stored
        return find_tclsh_executable() or ""

    @tcl_executable.setter
    def tcl_executable(self, value: str) -> None:
        self._set("tcl_executable", value)

    @property
    def osvvm_scripts_path(self) -> str:
        """Directory containing ``StartUp.tcl``, or the OsvvmLibraries root."""
        return self._settings.value("osvvm_scripts_path", "", str) or ""

    @osvvm_scripts_path.setter
    def osvvm_scripts_path(self, value: str) -> None:
        self._set("osvvm_scripts_path", value)

    @property
    def osvvm_html_report(self) -> str:
        """HTML report path shown after OSVVM Build (relative to the .pro dir)."""
        stored = self._settings.value("osvvm_html_report", DEFAULT_OSVVM_HTML_REPORT, str)
        return (stored or DEFAULT_OSVVM_HTML_REPORT).strip() or DEFAULT_OSVVM_HTML_REPORT

    @osvvm_html_report.setter
    def osvvm_html_report(self, value: str) -> None:
        normalised = (value or "").strip() or DEFAULT_OSVVM_HTML_REPORT
        self._set("osvvm_html_report", normalised)
