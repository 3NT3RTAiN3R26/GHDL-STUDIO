"""Einfacher Syntax-Highlighter fuer VHDL-Quelltext."""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

_KEYWORDS = [
    "entity", "architecture", "is", "begin", "end", "process", "signal",
    "variable", "constant", "port", "generic", "map", "in", "out", "inout",
    "buffer", "component", "if", "then", "else", "elsif", "case", "when",
    "others", "for", "loop", "while", "generate", "library", "use", "all",
    "package", "body", "of", "return", "function", "procedure", "wait",
    "until", "std_logic", "std_logic_vector", "unsigned", "signed",
    "integer", "boolean", "bit", "bit_vector", "type", "record", "array",
    "downto", "to", "not", "and", "or", "xor", "nand", "nor", "xnor",
    "rising_edge", "falling_edge", "report", "severity", "assert", "note",
    "warning", "error", "failure", "null",
]


class VhdlHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        pattern = r"\b(" + "|".join(re.escape(k) for k in _KEYWORDS) + r")\b"
        self._rules.append((QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self._rules.append((QRegularExpression(r'"[^"\n]*"'), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self._rules.append((QRegularExpression(r"\b[0-9]+\b"), number_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        self._rules.append((QRegularExpression(r"--[^\n]*"), comment_format))

    def highlightBlock(self, text: str) -> None:
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
