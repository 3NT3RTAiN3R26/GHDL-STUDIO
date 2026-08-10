"""Syntax highlighter for Verilog / SystemVerilog source."""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

_KEYWORDS = [
    "module",
    "endmodule",
    "macromodule",
    "primitive",
    "endprimitive",
    "input",
    "output",
    "inout",
    "wire",
    "reg",
    "logic",
    "bit",
    "byte",
    "int",
    "integer",
    "real",
    "realtime",
    "time",
    "string",
    "event",
    "supply0",
    "supply1",
    "tri",
    "triand",
    "trior",
    "tri0",
    "tri1",
    "wand",
    "wor",
    "signed",
    "unsigned",
    "parameter",
    "localparam",
    "defparam",
    "specparam",
    "always",
    "always_ff",
    "always_comb",
    "always_latch",
    "initial",
    "final",
    "assign",
    "deassign",
    "force",
    "release",
    "begin",
    "end",
    "if",
    "else",
    "case",
    "casex",
    "casez",
    "endcase",
    "default",
    "for",
    "foreach",
    "forever",
    "repeat",
    "while",
    "do",
    "wait",
    "disable",
    "fork",
    "join",
    "join_any",
    "join_none",
    "function",
    "endfunction",
    "task",
    "endtask",
    "generate",
    "endgenerate",
    "genvar",
    "posedge",
    "negedge",
    "edge",
    "or",
    "and",
    "nand",
    "nor",
    "xor",
    "xnor",
    "not",
    "buf",
    "typedef",
    "enum",
    "struct",
    "union",
    "packed",
    "void",
    "automatic",
    "static",
    "const",
    "var",
    "ref",
    "return",
    "break",
    "continue",
    "package",
    "endpackage",
    "import",
    "export",
    "interface",
    "endinterface",
    "modport",
    "clocking",
    "endclocking",
    "property",
    "endproperty",
    "sequence",
    "endsequence",
    "assert",
    "assume",
    "cover",
    "restrict",
    "unique",
    "priority",
    "context",
    "pure",
    "virtual",
    "extends",
    "super",
    "this",
    "new",
    "class",
    "endclass",
    "null",
]


class VerilogHighlighter(QSyntaxHighlighter):
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

        system_format = QTextCharFormat()
        system_format.setForeground(QColor("#dcdcaa"))
        self._rules.append((QRegularExpression(r"\$[A-Za-z_][A-Za-z0-9_$]*"), system_format))

        directive_format = QTextCharFormat()
        directive_format.setForeground(QColor("#c586c0"))
        self._rules.append((QRegularExpression(r"`[A-Za-z_][A-Za-z0-9_$]*"), directive_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))
        self._rules.append((QRegularExpression(r'"[^"\\]*(?:\\.[^"\\]*)*"'), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(?:[0-9]+'[sS]?[bBhHdDoO][0-9a-fA-FxXzZ_]+|[0-9]+(?:\.[0-9]+)?)\b"
                ),
                number_format,
            )
        )

        line_comment_format = QTextCharFormat()
        line_comment_format.setForeground(QColor("#6a9955"))
        self._rules.append((QRegularExpression(r"//[^\n]*"), line_comment_format))

        self._block_comment_format = QTextCharFormat()
        self._block_comment_format.setForeground(QColor("#6a9955"))
        self._block_comment_start = QRegularExpression(r"/\*")
        self._block_comment_end = QRegularExpression(r"\*/")

    def highlightBlock(self, text: str) -> None:
        for regex, fmt in self._rules:
            it = regex.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        self._highlight_block_comments(text)

    def _highlight_block_comments(self, text: str) -> None:
        self.setCurrentBlockState(0)
        start_index = 0
        if self.previousBlockState() != 1:
            match = self._block_comment_start.match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1

        while start_index >= 0:
            end_match = self._block_comment_end.match(text, start_index)
            if end_match.hasMatch():
                length = end_match.capturedEnd() - start_index
                next_start = end_match.capturedEnd()
            else:
                self.setCurrentBlockState(1)
                length = len(text) - start_index
                next_start = -1
            self.setFormat(start_index, length, self._block_comment_format)
            if next_start < 0:
                break
            match = self._block_comment_start.match(text, next_start)
            start_index = match.capturedStart() if match.hasMatch() else -1
