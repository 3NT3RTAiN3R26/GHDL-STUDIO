"""Tests for post-Run waveform resolution (Surfer / internal viewer)."""

from pathlib import Path

from ghdl_studio.main_window import resolve_existing_waveform


def test_resolve_existing_waveform_prefers_existing_file(tmp_path):
    vcd = tmp_path / "tb.vcd"
    vcd.write_text("$enddefinitions $end\n", encoding="utf-8")
    assert resolve_existing_waveform(vcd) == vcd.resolve()


def test_resolve_existing_waveform_falls_back_to_ghw(tmp_path):
    ghw = tmp_path / "tb.ghw"
    ghw.write_bytes(b"GHDLwave")
    missing_vcd = tmp_path / "tb.vcd"
    assert resolve_existing_waveform(missing_vcd) == ghw.resolve()


def test_resolve_existing_waveform_falls_back_to_vcd(tmp_path):
    vcd = tmp_path / "tb.vcd"
    vcd.write_text("$enddefinitions $end\n", encoding="utf-8")
    missing_ghw = tmp_path / "tb.ghw"
    assert resolve_existing_waveform(missing_ghw) == vcd.resolve()


def test_resolve_existing_waveform_returns_none_when_missing(tmp_path):
    assert resolve_existing_waveform(tmp_path / "missing.vcd") is None
