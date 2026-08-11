"""Rich-text log console for GHDL Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QTextEdit

from ghdl_studio.ghdl_locations import (
    GhdlLocation,
    parse_ghdl_file_header,
    parse_ghdl_location,
)


class _LocationBlockData(QTextBlockUserData):
    """Stores a clickable GHDL location on a console text block."""

    def __init__(self, location: GhdlLocation) -> None:
        super().__init__()
        self.location = location


def is_osvvm_transcript_line(line: str) -> bool:
    """True when *line* is OSVVM AlertLog / Transcript text, not a tool error.

    OSVVM prints ``%%`` transcripts (``Log``, ``DONE``, ``PASSED``, ``ALWAYS``, …)
    to stderr under GHDL Studio. Those must not get the UI ``Error:`` prefix.
    """
    stripped = line.lstrip()
    # Streams sometimes already carry a leading "Error:" from earlier wrapping.
    if stripped.startswith("Error:"):
        stripped = stripped[len("Error:") :].lstrip()
    if stripped.startswith("%%"):
        return True
    # Avoid classifying real GHDL compile/elab failures that merely mention PASSED.
    lower = stripped.lower()
    if ":error:" in lower or "simulation failed" in lower:
        return False
    # Compact DONE / Affirmation summaries (with or without leading %% / Log).
    compact = " ".join(stripped.split())
    if compact.startswith("DONE ") and any(
        compact.endswith(suf) or f" {suf}" in compact
        for suf in ("PASSED", "FAILED")
    ):
        return True
    if "Affirmations Checked:" in stripped or compact.startswith("Passed:"):
        return True
    # OSVVM AlertLog levels / DONE lines (with or without an explicit "Log" token).
    for token in (
        "    Log    ",
        "    DONE   ",
        "    DONE    ",
        " Log ",
        " DONE ",
        " PASSED ",
        " ALWAYS ",
        " FAILED ",
        " ERROR ",
        " WARNING ",
        " INFO ",
        " DEBUG ",
    ):
        if token in stripped:
            if stripped.startswith("%%") or "%%" in stripped[:8] or "    Log" in stripped or "    DONE" in stripped:
                return True
            # Compact forms without leading %% (some OSVVM/report paths).
            if any(
                marker in stripped
                for marker in (
                    "    Log    PASSED",
                    "    Log    ALWAYS",
                    "    Log    FAILED",
                    "    DONE   PASSED",
                    "    DONE    PASSED",
                )
            ):
                return True
    return False


def strip_process_error_prefix_for_osvvm(line: str) -> str:
    """If *line* is ``Error:`` + OSVVM transcript, return the transcript only."""
    stripped = line.lstrip()
    if not stripped.startswith("Error:"):
        return line
    rest = stripped[len("Error:") :]
    # Preserve a single leading space after the prefix when present.
    candidate = rest.lstrip(" ")
    if is_osvvm_transcript_line(candidate) or is_osvvm_transcript_line(rest):
        # Prefer keeping the original spacing after "Error:" when it was "Error: %%..."
        if rest.startswith(" "):
            return rest[1:] if rest.startswith("  ") is False else rest.lstrip()
        return rest.lstrip()
    return line


def classify_log_line(line: str, *, from_stderr: bool = False) -> str:
    """Return ``error``, ``warning``, or ``info`` for console coloring.

    OSVVM transcript on stderr is ``info`` so it is not painted as a failure.
    """
    text = line.rstrip("\r\n")
    if is_osvvm_transcript_line(text):
        return "info"
    lower = text.lower()
    if ":error:" in lower or lower.startswith("error:") or "simulation failed" in lower:
        return "error"
    if ":warning:" in lower or lower.startswith("warning:"):
        return "warning"
    if from_stderr:
        # GHDL often writes progress to stderr; only treat as error when it looks like one.
        if any(
            marker in lower
            for marker in (
                "error:",
                ":error:",
                "failed",
                "fatal",
                "cannot load",
                "compilation error",
            )
        ):
            return "error"
        return "info"
    return "info"


class LogConsole(QTextEdit):
    """Append-only log view with simple coloring.

    Click (or double-click) a GHDL diagnostic to open the source location
    (emits :attr:`location_activated`). Supports both classic
    ``file:line:col:error:`` lines and the split form used by some GHDL
    builds::

        /path/to/file.vhd:
        24:31:error: missing ";" …
    """

    location_activated = Signal(object)  # GhdlLocation

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setToolTip(
            "Click a GHDL diagnostic (underlined) to open the source in the Editor."
        )
        self._last_source_path: str | None = None

    def append_command(self, text: str) -> None:
        """Highlight an invoked command line (e.g. ``$ ghdl -a …``)."""
        self._append(text, QColor("#569cd6"))

    def append_output(self, text: str) -> None:
        self._append(text, QColor("#d4d4d4"))

    def append_error(self, text: str) -> None:
        # Keep the visible Error: prefix only for real failures (caller decides).
        payload = text if text.lstrip().startswith("Error:") else f"Error: {text}"
        self._append(payload, QColor("#f44747"), linkify=True)

    def append_warning(self, text: str) -> None:
        self._append(text, QColor("#dcdcaa"), linkify=True)

    def append_success(self, text: str) -> None:
        """Highlight a successful completion / status line."""
        self._append(text, QColor("#4ec9b0"))

    def append_history(self, text: str) -> None:
        """Highlight a session build-history line."""
        self._append(text, QColor("#9cdcfe"))

    def _append(self, text: str, color: QColor, *, linkify: bool = False) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        payload = text if text.endswith("\n") else text + "\n"

        header = parse_ghdl_file_header(payload) if linkify else None
        if header:
            self._last_source_path = header

        location = None
        if linkify:
            location = parse_ghdl_location(payload, default_path=self._last_source_path)
            # Lone ``file.vhd:`` headers are also clickable (open at line 1).
            if location is None and header:
                location = GhdlLocation(path=header, line=1, column=1)

        block_start = cursor.position()
        if location is None:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.insertText(payload, fmt)
        else:
            # Underline the whole diagnostic line so it is obviously clickable.
            link_fmt = QTextCharFormat()
            link_fmt.setForeground(color)
            link_fmt.setFontUnderline(True)
            link_fmt.setUnderlineColor(color)
            cursor.insertText(payload, link_fmt)

        # Attach location to the block we just wrote (before the trailing newline
        # the block of interest is at block_start).
        if location is not None:
            anchor = self.document().findBlock(block_start)
            if anchor.isValid():
                anchor.setUserData(_LocationBlockData(location))

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _location_at(self, pos) -> GhdlLocation | None:
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        data = block.userData()
        if isinstance(data, _LocationBlockData):
            return data.location
        # Fallback for blocks without user data (e.g. older lines / tests).
        return parse_ghdl_location(block.text(), default_path=self._last_source_path)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Prefer click over double-click (WSL/WSLg often eats or delays double-clicks).
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self.textCursor().hasSelection()
        ):
            location = self._location_at(event.position().toPoint())
            if location is not None:
                self.location_activated.emit(location)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._location_at(event.position().toPoint()) is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)
