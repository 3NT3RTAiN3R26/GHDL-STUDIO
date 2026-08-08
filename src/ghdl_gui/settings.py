"""Persistente Anwendungseinstellungen ueber QSettings.

QSettings speichert plattformabhaengig (Registry unter Windows, plist unter
macOS, ini-Dateien unter Linux) und sorgt so dafuer, dass sich die GUI auf
allen unterstuetzten Plattformen gleich verhaelt.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from ghdl_gui.ghdl_commands import DEFAULT_STD, find_ghdl_executable

ORG_NAME = "GhdlGui"
APP_NAME = "GhdlGui"


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings(ORG_NAME, APP_NAME)

    @property
    def ghdl_executable(self) -> str:
        stored = self._settings.value("ghdl_executable", "", str)
        if stored:
            return stored
        return find_ghdl_executable() or ""

    @ghdl_executable.setter
    def ghdl_executable(self, value: str) -> None:
        self._settings.setValue("ghdl_executable", value)

    @property
    def vhdl_std(self) -> str:
        return self._settings.value("vhdl_std", DEFAULT_STD, str)

    @vhdl_std.setter
    def vhdl_std(self, value: str) -> None:
        self._settings.setValue("vhdl_std", value)

    @property
    def last_project_dir(self) -> str:
        return self._settings.value("last_project_dir", "", str)

    @last_project_dir.setter
    def last_project_dir(self, value: str) -> None:
        self._settings.setValue("last_project_dir", value)

    @property
    def recent_files(self) -> list[str]:
        return self._settings.value("recent_files", [], list) or []

    @recent_files.setter
    def recent_files(self, value: list[str]) -> None:
        self._settings.setValue("recent_files", value)
