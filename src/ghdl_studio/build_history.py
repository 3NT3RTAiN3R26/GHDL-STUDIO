"""Session build / run history helpers (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BuildHistoryEntry:
    """One finished Analyze / Elaborate / Run / Build invocation."""

    label: str
    exit_code: int
    timestamp: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def make_build_history_entry(label: str, exit_code: int, *, when: datetime | None = None) -> BuildHistoryEntry:
    stamp = (when or datetime.now()).strftime("%H:%M:%S")
    return BuildHistoryEntry(label=label, exit_code=exit_code, timestamp=stamp)


def format_build_history_line(entry: BuildHistoryEntry) -> str:
    """Human-readable history line for the Output dock."""
    status = "ok" if entry.ok else "FAILED"
    return f"[History {entry.timestamp}] {entry.label} → exit {entry.exit_code} ({status})"


def append_build_history(
    history: list[BuildHistoryEntry],
    entry: BuildHistoryEntry,
    *,
    limit: int = 20,
) -> list[BuildHistoryEntry]:
    """Return a new list with *entry* appended, capped at *limit* (oldest dropped)."""
    updated = list(history)
    updated.append(entry)
    if limit > 0 and len(updated) > limit:
        updated = updated[-limit:]
    return updated
