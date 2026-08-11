"""Parse GHDL diagnostic locations (``file:line:col:error: …``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Classic single-line GHDL compile diagnostics:
#   bad.vhd:5:3:error: no declaration for "x"
#   /abs/path.vhd:2:30:warning: …
# After LogConsole wrapping:
#   Error: bad.vhd:5:3:error: …
_LOCATION_RE = re.compile(
    r"^(?:Error:\s*)?"
    r"(?P<path>.+?)"
    r":(?P<line>\d+)"
    r":(?P<col>\d+)"
    r":(?P<severity>error|warning|note)\b"
    r"(?:\s*:\s*(?P<message>.*))?",
    re.IGNORECASE,
)

# Split style (some GHDL / long-path builds):
#   /path/to/file.vhd:
#   24:31:error: missing ";" at end of statement
_FILE_HEADER_RE = re.compile(
    r"^(?:Error:\s*)?(?P<path>.+\.(?:vhd|vhdl|v|sv|vh|svh))\s*:\s*$",
    re.IGNORECASE,
)
_LINE_ONLY_RE = re.compile(
    r"^(?:Error:\s*)?(?P<line>\d+):(?P<col>\d+):(?P<severity>error|warning|note)\b"
    r"(?:\s*:\s*(?P<message>.*))?",
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
    severity: str = "error"
    message: str = ""


def strip_error_prefix(line: str) -> str:
    """Remove a leading UI ``Error:`` prefix if present."""
    stripped = line.strip()
    if stripped.startswith("Error:"):
        return stripped[len("Error:") :].lstrip()
    return stripped


def parse_ghdl_file_header(line: str) -> str | None:
    """Return a source path when *line* is a lone ``path:`` header."""
    text = line.strip()
    match = _FILE_HEADER_RE.match(text)
    if match is None:
        return None
    path = match.group("path").strip()
    name = Path(path).name.lower()
    if name in _NON_SOURCE_NAMES:
        return None
    return path


def parse_ghdl_location(
    line: str,
    *,
    default_path: str | None = None,
) -> GhdlLocation | None:
    """Return a :class:`GhdlLocation` if *line* looks like a GHDL file diagnostic.

    Supports:
    - ``file.vhd:10:5:error: …``
    - ``Error: file.vhd:10:5:error: …``
    - ``24:31:error: …`` when *default_path* was set by a preceding ``file.vhd:`` header
    """
    text = line.strip()
    if not text:
        return None

    # Prefer classic path:line:col form first.
    match = _LOCATION_RE.match(text)
    if match is not None:
        path = match.group("path").strip()
        if path and path.lower() not in _NON_SOURCE_NAMES:
            name = Path(path).name.lower()
            if name not in _NON_SOURCE_NAMES and not path.isdigit():
                try:
                    line_no = int(match.group("line"))
                    col_no = int(match.group("col"))
                except ValueError:
                    return None
                if line_no >= 1 and col_no >= 1:
                    severity = (match.group("severity") or "error").lower()
                    message = (match.group("message") or "").strip()
                    return GhdlLocation(
                        path=path,
                        line=line_no,
                        column=col_no,
                        severity=severity,
                        message=message,
                    )

    # Split style: "24:31:error: …" using the last seen file header.
    if default_path:
        line_only = _LINE_ONLY_RE.match(text)
        if line_only is not None:
            try:
                line_no = int(line_only.group("line"))
                col_no = int(line_only.group("col"))
            except ValueError:
                return None
            if line_no >= 1 and col_no >= 1:
                severity = (line_only.group("severity") or "error").lower()
                message = (line_only.group("message") or "").strip()
                return GhdlLocation(
                    path=default_path,
                    line=line_no,
                    column=col_no,
                    severity=severity,
                    message=message,
                )

    return None


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
