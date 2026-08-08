"""Erkennung von VHDL-Entities und Verilog-Modulen in Quelldateien.

Qt-frei und damit unabhaengig von einer grafischen Umgebung testbar. Wird
u. a. genutzt, um dem Nutzer eine klickbare Auswahl moeglicher
Top-Level-Einheiten anzubieten, statt den Namen manuell eintippen zu
muessen.
"""

from __future__ import annotations

import re
from pathlib import Path

VHDL_EXTENSIONS = (".vhd", ".vhdl")
VERILOG_EXTENSIONS = (".v", ".sv", ".vh", ".svh")
# Stimulus / reference data opened by testbenches at simulation time (not analysed).
DATA_FILE_EXTENSIONS = (".txt", ".csv", ".dat", ".hex", ".mem", ".bin", ".yml", ".yaml")

_ENTITY_PATTERN = re.compile(r"\bentity\s+([A-Za-z_][A-Za-z0-9_]*)\s+is\b", re.IGNORECASE)
_VERILOG_MODULE_PATTERN = re.compile(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\b", re.IGNORECASE)


def is_vhdl_file(path: str) -> bool:
    return Path(path).suffix.lower() in VHDL_EXTENSIONS


def is_verilog_file(path: str) -> bool:
    return Path(path).suffix.lower() in VERILOG_EXTENSIONS


def is_data_file(path: str) -> bool:
    """Return True for non-HDL stimulus/reference files (e.g. ``.txt``)."""
    return Path(path).suffix.lower() in DATA_FILE_EXTENSIONS


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def find_vhdl_entities(paths: list[str]) -> list[str]:
    """Durchsucht die angegebenen VHDL-Dateien nach ``entity <name> is``.

    Nicht-VHDL-Dateien in ``paths`` werden ignoriert. Die Reihenfolge der
    Ergebnisse folgt der ersten Fundstelle, Duplikate (unabhaengig von
    Gross-/Kleinschreibung) werden entfernt.
    """
    entities: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not is_vhdl_file(path):
            continue
        for match in _ENTITY_PATTERN.finditer(_read_text(path)):
            name = match.group(1)
            key = name.lower()
            if key not in seen:
                seen.add(key)
                entities.append(name)
    return entities


def find_verilog_modules(paths: list[str]) -> list[str]:
    """Durchsucht die angegebenen Verilog/SystemVerilog-Dateien nach ``module <name>``."""
    modules: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not is_verilog_file(path):
            continue
        for match in _VERILOG_MODULE_PATTERN.finditer(_read_text(path)):
            name = match.group(1)
            key = name.lower()
            if key not in seen:
                seen.add(key)
                modules.append(name)
    return modules
