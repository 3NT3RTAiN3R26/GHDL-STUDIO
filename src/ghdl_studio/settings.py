"""Persistente Anwendungseinstellungen ueber QSettings.

QSettings speichert plattformabhaengig (Registry unter Windows, plist unter
macOS, ini-Dateien unter Linux) und sorgt so dafuer, dass sich die GUI auf
allen unterstuetzten Plattformen gleich verhaelt.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    DEFAULT_STD,
    find_ghdl_executable,
)
from ghdl_studio.gtkwave_embed import find_gtkwave_executable

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
    def gtkwave_executable(self) -> str:
        stored = self._settings.value("gtkwave_executable", "", str)
        if stored:
            return stored
        return find_gtkwave_executable() or ""

    @gtkwave_executable.setter
    def gtkwave_executable(self, value: str) -> None:
        self._set("gtkwave_executable", value)

    @property
    def gtkwave_integration_enabled(self) -> bool:
        return self._settings.value("gtkwave_integration_enabled", True, bool)

    @gtkwave_integration_enabled.setter
    def gtkwave_integration_enabled(self, value: bool) -> None:
        self._set("gtkwave_integration_enabled", value)

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
