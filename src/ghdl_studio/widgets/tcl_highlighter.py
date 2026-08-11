"""Syntax highlighter for Tcl / OSVVM ``.pro`` scripts."""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

# Core Tcl language words.
_TCL_KEYWORDS = [
    "after",
    "append",
    "array",
    "break",
    "catch",
    "cd",
    "concat",
    "continue",
    "dict",
    "else",
    "elseif",
    "encoding",
    "eof",
    "error",
    "eval",
    "exec",
    "exit",
    "expr",
    "file",
    "flush",
    "for",
    "foreach",
    "format",
    "gets",
    "glob",
    "global",
    "if",
    "incr",
    "info",
    "join",
    "lappend",
    "lassign",
    "lindex",
    "linsert",
    "list",
    "llength",
    "lrange",
    "lreplace",
    "lsearch",
    "lsort",
    "namespace",
    "open",
    "package",
    "pid",
    "proc",
    "puts",
    "pwd",
    "read",
    "regexp",
    "regsub",
    "rename",
    "return",
    "scan",
    "set",
    "source",
    "split",
    "string",
    "subst",
    "switch",
    "trace",
    "unset",
    "uplevel",
    "upvar",
    "variable",
    "while",
]

# Common OSVVM Scripts / VendorScripts commands used in ``.pro`` files.
_OSVVM_COMMANDS = [
    "analyze",
    "simulate",
    "library",
    "include",
    "build",
    "RunTest",
    "TestName",
    "SetVHDLVersion",
    "SetSaveWaves",
    "SetCoverageAnalyzeEnable",
    "SetCoverageSimulateEnable",
    "SetSimulator",
    "SetLibraryDirectory",
    "LinkLibraryDirectory",
    "SetInteractiveMode",
    "SetDebugMode",
    "SetLogEnable",
    "SetAlertLogOptions",
    "Library",
    "Analyze",
    "Simulate",
    "Include",
]


class TclHighlighter(QSyntaxHighlighter):
    """Line-oriented highlighting for Tcl and OSVVM ``.pro`` scripts."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = _TCL_KEYWORDS + _OSVVM_COMMANDS
        pattern = r"\b(" + "|".join(re.escape(k) for k in keywords) + r")\b"
        self._rules.append(
            (
                QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption),
                keyword_format,
            )
        )

        # Variables: $foo, $::ns::bar, ${foo}
        var_format = QTextCharFormat()
        var_format.setForeground(QColor("#dcdcaa"))
        self._rules.append(
            (
                QRegularExpression(
                    r"\$(?:\{[^}\n]+\}|[A-Za-z_:][A-Za-z0-9_:]*)"
                ),
                var_format,
            )
        )

        # Command substitutions [ ... ] (single-line)
        cmd_format = QTextCharFormat()
        cmd_format.setForeground(QColor("#c586c0"))
        self._rules.append((QRegularExpression(r"\[[^\]\n]*\]"), cmd_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self._rules.append(
            (QRegularExpression(r'"(?:\\.|[^"\\])*"'), string_format)
        )
        # Braced words { ... } on one line (common Tcl quoting)
        self._rules.append((QRegularExpression(r"\{[^{}\n]*\}"), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self._rules.append(
            (QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?\b"), number_format)
        )

        # Comments last so they win over keywords/strings on the same span.
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self._rules.append((QRegularExpression(r"#[^\n]*"), comment_format))

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
