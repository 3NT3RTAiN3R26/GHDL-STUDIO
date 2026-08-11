"""Tests for session build history helpers."""

from datetime import datetime

from ghdl_studio.build_history import (
    append_build_history,
    format_build_history_line,
    make_build_history_entry,
)


def test_make_and_format_history_entry():
    entry = make_build_history_entry(
        "Analyze",
        0,
        when=datetime(2026, 8, 11, 16, 30, 5),
    )
    assert entry.label == "Analyze"
    assert entry.exit_code == 0
    assert entry.ok
    assert entry.timestamp == "16:30:05"
    assert format_build_history_line(entry) == (
        "[History 16:30:05] Analyze → exit 0 (ok)"
    )


def test_format_failed_history_entry():
    entry = make_build_history_entry("Run", 1, when=datetime(2026, 1, 1, 9, 0, 0))
    assert not entry.ok
    assert "FAILED" in format_build_history_line(entry)


def test_append_build_history_caps_limit():
    history = []
    for i in range(5):
        history = append_build_history(
            history,
            make_build_history_entry("Analyze", i, when=datetime(2026, 1, 1, 0, 0, i)),
            limit=3,
        )
    assert len(history) == 3
    assert [e.exit_code for e in history] == [2, 3, 4]
