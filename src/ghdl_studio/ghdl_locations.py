"""Parse GHDL diagnostic locations (``file:line:col:error: …``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# GHDL compile diagnostics:
#   bad.vhd:5:3:error: no declaration for "x"
#   /abs/path.vhd:2:30:warning: …
# After LogConsole wrapping:
#   Error: bad.vhd:5:3:error: …
_LOCATION_RE = re.compile(
    r"^(?:Error:\s*)?"
    r"(?P<path>.+?)"
    r":(?P<line>\d+)"
    r":(?P<col>\d+)"
    r":(?:error|warning|note)\b",
    re.IGNORECASE,
)

# Tool binaries / elaborated executables — not source locations.
_NON_SOURCE_NAMES = frozenset(
    {
        "ghdl",
        "ghdl-mcode",
        "ghdl-gcc",
        "ghdl-llvm",
        "error",
        "warning",
        "note",
    }
)


@dataclass(frozen=True)
class GhdlLocation:
    """A source location extracted from a GHDL diagnostic line."""

    path: str
    line: int
    column: int


def parse_ghdl_location(line: str) -> GhdlLocation | None:
    """Return a :class:`GhdlLocation` if *line* looks like a GHDL file diagnostic."""
    text = line.strip()
    if not text:
        return None
    match = _LOCATION_RE.match(text)
    if match is None:
        return None
    path = match.group("path").strip()
    if not path or path.lower() in _NON_SOURCE_NAMES:
        return None
    # Bare tool names with drive-less prefixes like "./sim:error:" lack line:col
    # and never match; still reject obvious non-files (no suffix, only digits…).
    name = Path(path).name.lower()
    if name in _NON_SOURCE_NAMES:
        return None
    try:
        line_no = int(match.group("line"))
        col_no = int(match.group("col"))
    except ValueError:
        return None
    if line_no < 1 or col_no < 1:
        return None
    return GhdlLocation(path=path, line=line_no, column=col_no)


def resolve_ghdl_location_path(
    reported: str,
    *,
    search_roots: list[str] | None = None,
    known_files: list[str] | None = None,
) -> str | None:
    """Resolve a GHDL-reported path to an existing file on disk.

    Tries absolute path, then each search root, then basename match against
    *known_files* (project list).
    """
    candidate = Path(reported).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())

    # Relative to known roots (project root, output cwd, …).
    for root in search_roots or []:
        if not root:
            continue
        joined = Path(root) / reported
        if joined.is_file():
            return str(joined.resolve())
        # GHDL sometimes strips directories; try basename under root.
        by_name = Path(root) / Path(reported).name
        if by_name.is_file():
            return str(by_name.resolve())

    reported_name = Path(reported).name.lower()
    for known in known_files or []:
        known_path = Path(known)
        if known_path.name.lower() == reported_name and known_path.is_file():
            return str(known_path.resolve())
        try:
            if known_path.resolve().as_posix().endswith(Path(reported).as_posix()):
                return str(known_path.resolve())
        except OSError:
            continue
    return None
