"""Rich-text log console for GHDL Studio."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from ghdl_studio.ghdl_locations import parse_ghdl_location


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

    Double-click a GHDL ``file:line:col:error:`` / ``warning:`` line to open
    the source location (emits :attr:`location_activated`).
    """

    location_activated = Signal(object)  # GhdlLocation

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setToolTip(
            "Double-click a GHDL diagnostic (file:line:col:error:) to open the source."
        )

    def append_command(self, text: str) -> None:
        """Highlight an invoked command line (e.g. ``$ ghdl -a …``)."""
        self._append(text, QColor("#569cd6"))

    def append_output(self, text: str) -> None:
        self._append(text, QColor("#d4d4d4"))

    def append_error(self, text: str) -> None:
        # Keep the visible Error: prefix only for real failures (caller decides).
        payload = text if text.lstrip().startswith("Error:") else f"Error: {text}"
        self._append(payload, QColor("#f44747"), underline_location=True)

    def append_warning(self, text: str) -> None:
        self._append(text, QColor("#dcdcaa"), underline_location=True)

    def append_success(self, text: str) -> None:
        """Highlight a successful completion / status line."""
        self._append(text, QColor("#4ec9b0"))

    def _append(self, text: str, color: QColor, *, underline_location: bool = False) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        payload = text if text.endswith("\n") else text + "\n"
        location = parse_ghdl_location(payload) if underline_location else None
        if location is None:
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor.insertText(payload, fmt)
        else:
            # Underline the path:line:col portion so clickable diagnostics stand out.
            prefix_match_end = payload.find(f":{location.line}:{location.column}:")
            if prefix_match_end < 0:
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                cursor.insertText(payload, fmt)
            else:
                # Include path + :line:col
                loc_end = prefix_match_end + len(f":{location.line}:{location.column}")
                body = payload
                link_fmt = QTextCharFormat()
                link_fmt.setForeground(color)
                link_fmt.setFontUnderline(True)
                link_fmt.setUnderlineColor(color)
                normal_fmt = QTextCharFormat()
                normal_fmt.setForeground(color)
                cursor.insertText(body[:loc_end], link_fmt)
                cursor.insertText(body[loc_end:], normal_fmt)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            block = cursor.block()
            location = parse_ghdl_location(block.text())
            if location is not None:
                self.location_activated.emit(location)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        cursor = self.cursorForPosition(event.position().toPoint())
        if parse_ghdl_location(cursor.block().text()) is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)
