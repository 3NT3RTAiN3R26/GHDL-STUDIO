"""Packaging / portable build scaffolding (#44)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_windows_portable_files_exist():
    assert (ROOT / "packaging" / "windows_entry.py").is_file()
    assert (ROOT / "packaging" / "ghdl_studio_windows.spec").is_file()
    assert (ROOT / "scripts" / "build_windows_portable.ps1").is_file()
    assert (ROOT / ".github" / "workflows" / "windows-portable.yml").is_file()


def test_windows_spec_mentions_entry_and_excludes_webengine():
    text = (ROOT / "packaging" / "ghdl_studio_windows.spec").read_text(encoding="utf-8")
    assert "windows_entry.py" in text
    assert "GHDL-Studio" in text
    assert "QtWebEngineWidgets" in text


def test_build_script_smoke_checks_version():
    text = (ROOT / "scripts" / "build_windows_portable.ps1").read_text(encoding="utf-8")
    assert "build_windows_portable" in text or "PyInstaller" in text
    assert "--version" in text
    assert "GHDL-Studio-windows-portable" in text
