"""Reine Hilfsfunktionen zum Aufbau von GHDL-Kommandozeilen.

Dieses Modul haengt bewusst nicht von Qt ab, damit es unabhaengig von einer
grafischen Umgebung (und ohne installiertes PySide6) getestet werden kann.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

VHDL_STANDARDS = ("87", "93", "93c", "00", "02", "08")
DEFAULT_STD = "08"

# Werden standardmaessig bei jedem "ghdl -a" mitgegeben. Sinnvoll z. B. fuer
# GHDL-Builds mit dem GCC-Backend, bei denen Coverage-Instrumentierung
# (gcov) und PIE-Kompatibilitaet gewuenscht sind. Ueber den
# Einstellungsdialog vom Nutzer anpassbar.
DEFAULT_ANALYZE_EXTRA_ARGS = (
    "-Wc,-fprofile-arcs",
    "-Wc,-ftest-coverage",
    "-fsynopsys",
    "-fPIE",
)

# Werden standardmaessig bei jedem "ghdl -e" mitgegeben. -Wl,-lgcov linkt die
# gcov-Laufzeitbibliothek (passend zur Coverage-Instrumentierung aus dem
# Analyze-Schritt), -fsynopsys/-fPIE muessen konsistent mit dem
# Analyze-Aufruf gesetzt werden. Ueber den Einstellungsdialog vom Nutzer
# anpassbar.
DEFAULT_ELABORATE_EXTRA_ARGS = (
    "-Wl,-lgcov",
    "-fsynopsys",
    "-fPIE",
)

# Wird standardmaessig bei jedem "ghdl -r" mitgegeben, damit die
# Synopsys-Erweiterungen konsistent mit Analyze/Elaborate aktiv sind. Ueber
# den Einstellungsdialog vom Nutzer anpassbar.
DEFAULT_RUN_EXTRA_ARGS = (
    "-fsynopsys",
)


def find_ghdl_executable() -> str | None:
    """Sucht die ghdl-Executable im PATH und gibt den vollen Pfad zurueck."""
    return shutil.which("ghdl")


@dataclass
class GhdlVersionInfo:
    raw: str
    version: str | None = None
    backend: str | None = None


def parse_ghdl_version(output: str) -> GhdlVersionInfo:
    """Parst die Ausgabe von ``ghdl --version`` in ein GhdlVersionInfo-Objekt."""
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    version_match = re.search(r"GHDL\s+([0-9][\w.\-]*)", first_line)
    backend_match = re.search(r"\((.*?)\)", first_line)
    return GhdlVersionInfo(
        raw=first_line,
        version=version_match.group(1) if version_match else None,
        backend=backend_match.group(1) if backend_match else None,
    )


def get_ghdl_version(executable: str, timeout: float = 5.0) -> GhdlVersionInfo:
    """Ruft ``<executable> --version`` synchron auf und parst das Ergebnis."""
    result = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return parse_ghdl_version(result.stdout or result.stderr)


def build_analyze_args(
    files: list[str],
    std: str = DEFAULT_STD,
    work_dir: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Baut die Argumente fuer ``ghdl -a`` (Analyze) auf."""
    if not files:
        raise ValueError("Es muss mindestens eine VHDL-Datei angegeben werden.")
    args = ["-a", f"--std={std}"]
    if work_dir:
        args.append(f"--workdir={work_dir}")
    args.extend(extra_args or [])
    args.extend(files)
    return args


def build_elaborate_args(
    unit: str,
    std: str = DEFAULT_STD,
    work_dir: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Baut die Argumente fuer ``ghdl -e`` (Elaborate) auf."""
    if not unit:
        raise ValueError("Es muss eine Top-Level-Entity angegeben werden.")
    args = ["-e", f"--std={std}"]
    if work_dir:
        args.append(f"--workdir={work_dir}")
    args.extend(extra_args or [])
    args.append(unit)
    return args


def build_run_args(
    unit: str,
    std: str = DEFAULT_STD,
    work_dir: str | None = None,
    vcd_path: str | None = None,
    stop_time: str | None = None,
    generics: dict[str, str] | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Baut die Argumente fuer ``ghdl -r`` (Run) auf.

    Laut GHDL-Syntax ``-r <[options...] unit [simulation_options...]>``
    muessen allgemeine Optionen wie ``-fsynopsys`` VOR dem Unit-Namen stehen,
    waehrend Generics, ``--vcd=`` und ``--stop-time=`` als Simulationsoptionen
    NACH dem Unit-Namen folgen. ``extra_args`` wird daher vor dem Unit-Namen
    eingefuegt, analog zu ``build_analyze_args``/``build_elaborate_args``.
    """
    if not unit:
        raise ValueError("Es muss eine Top-Level-Entity angegeben werden.")
    args = ["-r", f"--std={std}"]
    if work_dir:
        args.append(f"--workdir={work_dir}")
    args.extend(extra_args or [])
    args.append(unit)
    for key, value in (generics or {}).items():
        args.append(f"-g{key}={value}")
    if vcd_path:
        args.append(f"--vcd={vcd_path}")
    if stop_time:
        args.append(f"--stop-time={stop_time}")
    return args


@dataclass
class RunOptions:
    """Buendelt alle Einstellungen fuer einen Analyze/Elaborate/Run-Durchlauf."""

    top_unit: str = ""
    std: str = DEFAULT_STD
    work_dir: str | None = None
    stop_time: str | None = None
    generics: dict[str, str] = field(default_factory=dict)
    extra_analyze_args: list[str] = field(default_factory=lambda: list(DEFAULT_ANALYZE_EXTRA_ARGS))
    extra_elaborate_args: list[str] = field(default_factory=lambda: list(DEFAULT_ELABORATE_EXTRA_ARGS))
    extra_run_args: list[str] = field(default_factory=lambda: list(DEFAULT_RUN_EXTRA_ARGS))

    def vcd_path(self) -> str:
        base = Path(self.work_dir) if self.work_dir else Path(".")
        return str(base / f"{self.top_unit}.vcd")
