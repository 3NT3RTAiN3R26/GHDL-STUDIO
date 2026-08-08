"""Minimaler Parser fuer das Value Change Dump (VCD) Format.

GHDL erzeugt VCD-Dateien ueber ``--vcd=<datei>``. Dieser Parser deckt den
fuer Simulationsergebnisse relevanten Teil des Formats ab (Header mit
Signaldefinitionen und Zeitschritte mit Wertaenderungen), ohne externe
Abhaengigkeiten zu benoetigen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_TIME_UNIT_TO_FEMTOSECONDS: dict[str, float] = {
    "fs": 1,
    "ps": 1_000,
    "ns": 1_000_000,
    "us": 1_000_000_000,
    "ms": 1_000_000_000_000,
    "s": 1_000_000_000_000_000,
}

_TIMESCALE_RE = re.compile(r"([0-9]*\.?[0-9]+)\s*([a-zA-Z]+)")


def parse_timescale(timescale: str) -> tuple[float, str]:
    """Parst z. B. ``'1 ns'`` oder ``'10ps'`` in (Multiplikator, Einheit).

    Faellt auf ``(1.0, "ns")`` zurueck, falls die Zeichenkette nicht
    interpretiert werden kann.
    """
    match = _TIMESCALE_RE.search(timescale)
    if not match:
        return 1.0, "ns"
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit not in _TIME_UNIT_TO_FEMTOSECONDS:
        unit = "ns"
    return value, unit


def raw_time_to_femtoseconds(raw_time: float, timescale: str) -> float:
    """Rechnet einen VCD-Rohzeitwert (in Timescale-Einheiten) in Femtosekunden um."""
    multiplier, unit = parse_timescale(timescale)
    return raw_time * multiplier * _TIME_UNIT_TO_FEMTOSECONDS[unit]


def choose_time_unit(fs_value: float) -> str:
    """Waehlt eine sinnvolle Anzeigeeinheit (s/ms/us/ns/ps/fs) fuer einen Femtosekunden-Wert."""
    for unit in ("s", "ms", "us", "ns", "ps"):
        if abs(fs_value) >= _TIME_UNIT_TO_FEMTOSECONDS[unit]:
            return unit
    return "fs"


def format_femtoseconds_as(fs_value: float, unit: str) -> str:
    """Formatiert einen Femtosekunden-Wert in einer fest vorgegebenen Einheit."""
    factor = _TIME_UNIT_TO_FEMTOSECONDS.get(unit, 1)
    return f"{_trim_number(fs_value / factor)} {unit}"


def format_femtoseconds(fs_value: float) -> str:
    """Formatiert einen Femtosekunden-Wert menschenlesbar (z. B. ``'12.5 ns'``)."""
    if fs_value == 0:
        return "0 s"
    return format_femtoseconds_as(fs_value, choose_time_unit(fs_value))


def _trim_number(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def format_raw_time(raw_time: float, timescale: str) -> str:
    """Formatiert einen VCD-Rohzeitwert (in Timescale-Einheiten) menschenlesbar."""
    return format_femtoseconds(raw_time_to_femtoseconds(raw_time, timescale))


@dataclass
class VcdSignal:
    identifier: str
    name: str
    size: int
    scope: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.scope}.{self.name}" if self.scope else self.name


@dataclass
class VcdData:
    timescale: str = "1 ns"
    signals: dict[str, VcdSignal] = field(default_factory=dict)
    changes: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
    end_time: int = 0

    def ordered_signals(self) -> list[VcdSignal]:
        return list(self.signals.values())


def parse_vcd(path: str | Path) -> VcdData:
    """Liest eine VCD-Datei ein und liefert Signale + Wertaenderungen."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_vcd_text(text)


_TIMESCALE_BLOCK_RE = re.compile(r"\$timescale\s+(.*?)\s*\$end", re.DOTALL)


def parse_vcd_text(text: str) -> VcdData:
    data = VcdData()
    scope_stack: list[str] = []
    current_time = 0
    in_definitions = True

    # $timescale kann sowohl einzeilig (``$timescale 1ns $end``) als auch,
    # wie von GHDL erzeugt, mehrzeilig (``$timescale\n  1 fs\n$end``)
    # vorliegen. Ein Regex-Vorlauf ueber den kompletten Header erfasst beide
    # Faelle zuverlaessig, bevor die zeilenweise Verarbeitung unten greift.
    timescale_match = _TIMESCALE_BLOCK_RE.search(text)
    if timescale_match:
        collapsed = " ".join(timescale_match.group(1).split())
        if collapsed:
            data.timescale = collapsed

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if in_definitions:
            if line.startswith("$timescale"):
                continue
            if line.startswith("$scope"):
                tokens = line.split()
                if len(tokens) >= 3:
                    scope_stack.append(tokens[2])
                continue
            if line.startswith("$upscope"):
                if scope_stack:
                    scope_stack.pop()
                continue
            if line.startswith("$var"):
                tokens = line.split()
                # $var <type> <size> <id> <name> [<range>] $end
                if len(tokens) >= 5:
                    size = int(tokens[2])
                    identifier = tokens[3]
                    name = tokens[4]
                    scope = ".".join(scope_stack)
                    data.signals[identifier] = VcdSignal(
                        identifier=identifier, name=name, size=size, scope=scope
                    )
                    data.changes.setdefault(identifier, [])
                continue
            if line.startswith("$enddefinitions"):
                in_definitions = False
                continue
            # Ignoriere andere Header-Deklarationen ($date, $version, $comment, ...)
            continue

        # Wertaenderungs-Bereich
        if line.startswith("#"):
            try:
                current_time = int(line[1:])
            except ValueError:
                continue
            data.end_time = max(data.end_time, current_time)
            continue

        if line[0] in "01xXzZ":
            value, identifier = line[0], line[1:]
            if identifier in data.changes:
                data.changes[identifier].append((current_time, value))
            continue

        if line[0] in "bB":
            # Vektor-Wert, z.B. "b00101101 !" -> Wert und Identifier per Leerzeichen getrennt
            parts = line[1:].split()
            if len(parts) == 2:
                value, identifier = parts
                if identifier in data.changes:
                    data.changes[identifier].append((current_time, value))
            continue

        if line[0] in "rR":
            # Real-Wert, aehnlich wie Vektor behandelt (als String gespeichert)
            parts = line[1:].split()
            if len(parts) == 2:
                value, identifier = parts
                if identifier in data.changes:
                    data.changes[identifier].append((current_time, value))
            continue

    return data
