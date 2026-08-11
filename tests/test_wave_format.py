"""Tests for Normal-mode waveform dump format selection."""

from ghdl_studio.ghdl_commands import (
    WAVE_FORMAT_BOTH,
    WAVE_FORMAT_GHW,
    WAVE_FORMAT_VCD,
    build_simulation_option_args,
    normalize_wave_format,
    wave_dump_paths,
)


def test_normalize_wave_format():
    assert normalize_wave_format("VCD") == WAVE_FORMAT_VCD
    assert normalize_wave_format("ghw") == WAVE_FORMAT_GHW
    assert normalize_wave_format("both") == WAVE_FORMAT_BOTH
    assert normalize_wave_format("nope") == WAVE_FORMAT_BOTH
    assert normalize_wave_format(None) == WAVE_FORMAT_BOTH


def test_wave_dump_paths_vcd_only():
    vcd, ghw, pending = wave_dump_paths(
        WAVE_FORMAT_VCD,
        vcd_abs="/out/tb.vcd",
        ghw_abs="/out/tb.ghw",
    )
    assert vcd == "/out/tb.vcd"
    assert ghw is None
    assert pending == "/out/tb.vcd"
    assert build_simulation_option_args(vcd_path=vcd, wave_path=ghw) == [
        "--vcd=/out/tb.vcd"
    ]


def test_wave_dump_paths_ghw_only():
    vcd, ghw, pending = wave_dump_paths(
        WAVE_FORMAT_GHW,
        vcd_abs="/out/tb.vcd",
        ghw_abs="/out/tb.ghw",
    )
    assert vcd is None
    assert ghw == "/out/tb.ghw"
    assert pending == "/out/tb.ghw"
    assert build_simulation_option_args(vcd_path=vcd, wave_path=ghw) == [
        "--wave=/out/tb.ghw"
    ]


def test_wave_dump_paths_both_prefer_ghw():
    vcd, ghw, pending = wave_dump_paths(
        WAVE_FORMAT_BOTH,
        vcd_abs="/out/tb.vcd",
        ghw_abs="/out/tb.ghw",
        prefer_ghw=True,
    )
    assert vcd == "/out/tb.vcd"
    assert ghw == "/out/tb.ghw"
    assert pending == "/out/tb.ghw"
