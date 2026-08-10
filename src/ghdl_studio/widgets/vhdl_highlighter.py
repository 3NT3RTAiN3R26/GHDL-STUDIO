"""Einfacher Syntax-Highlighter fuer VHDL-Quelltext."""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

_KEYWORDS = [
    "abs", "access", "after", "alias", "all", "and", "architecture", "array",
    "assert", "attribute", "begin", "block", "body", "buffer", "bus", "case",
    "component", "configuration", "constant", "disconnect", "downto", "else",
    "elsif", "end", "entity", "exit", "file", "for", "function", "generate",
    "generic", "group", "guarded", "if", "impure", "in", "inertial", "inout",
    "is", "label", "library", "linkage", "literal", "loop", "map", "mod",
    "nand", "new", "next", "nor", "not", "null", "of", "on", "open", "or",
    "others", "out", "package", "port", "postponed", "procedure", "process",
    "pure", "range", "record", "register", "reject", "rem", "report", "return",
    "rol", "ror", "select", "severity", "shared", "signal", "sla", "sll", "sra",
    "srl", "subtype", "then", "to", "transport", "type", "unaffected", "units",
    "until", "use", "variable", "wait", "when", "while", "with", "xnor", "xor",
    # Common IEEE types / helpers (highlighted for readability).
    "std_logic", "std_logic_vector", "unsigned", "signed", "integer", "boolean",
    "bit", "bit_vector", "natural", "positive", "character", "string", "time",
    "rising_edge", "falling_edge", "note", "warning", "error", "failure",
]


class VhdlHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        pattern = r"\b(" + "|".join(re.escape(k) for k in _KEYWORDS) + r")\b"
        self._rules.append(
            (
                QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption),
                keyword_format,
            )
        )

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self._rules.append((QRegularExpression(r'"[^"\n]*"'), string_format))
        # Bit-string literals: B"1010", X"FF", O"77"
        self._rules.append(
            (
                QRegularExpression(
                    r"\b[bBxXoO]\"[0-9a-fA-F_]+\"",
                    QRegularExpression.PatternOption.CaseInsensitiveOption,
                ),
                string_format,
            )
        )

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self._rules.append(
            (QRegularExpression(r"\b[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?\b"), number_format)
        )

        # Comments last so they win over keywords/strings on the same span.
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self._rules.append((QRegularExpression(r"--[^\n]*"), comment_format))

    def highlightBlock(self, text: str) -> None:
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
