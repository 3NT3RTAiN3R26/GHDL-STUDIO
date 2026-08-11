"""Tests for recent ``.ghdlstudio`` project list in settings."""

from pathlib import Path

from ghdl_studio.settings import AppSettings


def test_remember_project_orders_and_prunes(tmp_path, monkeypatch):
    # Isolate QSettings in a temp org so we do not touch the real user config.
    from PySide6.QtCore import QSettings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = AppSettings()
    # Force ini under tmp by replacing the QSettings object.
    settings._settings = QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat)

    a = tmp_path / "a.ghdlstudio"
    b = tmp_path / "b.ghdlstudio"
    a.write_text("{}\n", encoding="utf-8")
    b.write_text("{}\n", encoding="utf-8")

    settings.remember_project(str(a), limit=5)
    settings.remember_project(str(b), limit=5)
    settings.remember_project(str(a), limit=5)
    recent = settings.recent_projects
    assert recent[0] == str(a.resolve())
    assert recent[1] == str(b.resolve())
    assert len(recent) == 2

    a.unlink()
    pruned = settings.recent_projects
    assert pruned == [str(b.resolve())]
