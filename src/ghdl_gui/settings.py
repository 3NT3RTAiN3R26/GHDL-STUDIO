"""Persistente Anwendungseinstellungen ueber QSettings.

QSettings speichert plattformabhaengig (Registry unter Windows, plist unter
macOS, ini-Dateien unter Linux) und sorgt so dafuer, dass sich die GUI auf
allen unterstuetzten Plattformen gleich verhaelt.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

from ghdl_gui.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_RUN_EXTRA_ARGS,
    DEFAULT_STD,
    find_ghdl_executable,
)
from ghdl_gui.gtkwave_embed import find_gtkwave_executable

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
    def analyze_extra_args(self) -> list[str]:
        if not self._settings.contains("analyze_extra_args"):
            return list(DEFAULT_ANALYZE_EXTRA_ARGS)
        stored = self._settings.value("analyze_extra_args", "", str)
        return stored.split()

    @analyze_extra_args.setter
    def analyze_extra_args(self, value: list[str]) -> None:
        self._settings.setValue("analyze_extra_args", " ".join(value))

    @property
    def elaborate_extra_args(self) -> list[str]:
        if not self._settings.contains("elaborate_extra_args"):
            return list(DEFAULT_ELABORATE_EXTRA_ARGS)
        stored = self._settings.value("elaborate_extra_args", "", str)
        return stored.split()

    @elaborate_extra_args.setter
    def elaborate_extra_args(self, value: list[str]) -> None:
        self._settings.setValue("elaborate_extra_args", " ".join(value))

    @property
    def run_extra_args(self) -> list[str]:
        if not self._settings.contains("run_extra_args"):
            return list(DEFAULT_RUN_EXTRA_ARGS)
        stored = self._settings.value("run_extra_args", "", str)
        return stored.split()

    @run_extra_args.setter
    def run_extra_args(self, value: list[str]) -> None:
        self._settings.setValue("run_extra_args", " ".join(value))

    @property
    def gtkwave_executable(self) -> str:
        stored = self._settings.value("gtkwave_executable", "", str)
        if stored:
            return stored
        return find_gtkwave_executable() or ""

    @gtkwave_executable.setter
    def gtkwave_executable(self, value: str) -> None:
        self._settings.setValue("gtkwave_executable", value)

    @property
    def gtkwave_integration_enabled(self) -> bool:
        return self._settings.value("gtkwave_integration_enabled", True, bool)

    @gtkwave_integration_enabled.setter
    def gtkwave_integration_enabled(self, value: bool) -> None:
        self._settings.setValue("gtkwave_integration_enabled", value)

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
