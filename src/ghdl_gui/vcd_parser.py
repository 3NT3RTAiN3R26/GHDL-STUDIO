"""Minimaler Parser fuer das Value Change Dump (VCD) Format.

GHDL erzeugt VCD-Dateien ueber ``--vcd=<datei>``. Dieser Parser deckt den
fuer Simulationsergebnisse relevanten Teil des Formats ab (Header mit
Signaldefinitionen und Zeitschritte mit Wertaenderungen), ohne externe
Abhaengigkeiten zu benoetigen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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


def parse_vcd_text(text: str) -> VcdData:
    data = VcdData()
    scope_stack: list[str] = []
    current_time = 0
    in_definitions = True

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if in_definitions:
            if line.startswith("$timescale"):
                parts = line.replace("$timescale", "").replace("$end", "").strip()
                if parts:
                    data.timescale = parts
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
