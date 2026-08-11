"""Tests for GHDL diagnostic location parsing."""

from pathlib import Path

from ghdl_studio.ghdl_locations import (
    GhdlLocation,
    parse_ghdl_file_header,
    parse_ghdl_location,
    resolve_ghdl_location_path,
)


def test_parse_relative_error_location():
    loc = parse_ghdl_location('bad.vhd:5:3:error: no declaration for "x"')
    assert loc == GhdlLocation(
        path="bad.vhd",
        line=5,
        column=3,
        severity="error",
        message='no declaration for "x"',
    )


def test_parse_absolute_warning_with_error_prefix():
    loc = parse_ghdl_location(
        "Error: /tmp/proj/rt.vhd:1:1:warning: entity \"e\" was also defined"
    )
    assert loc is not None
    assert loc.path == "/tmp/proj/rt.vhd"
    assert loc.line == 1
    assert loc.column == 1
    assert loc.severity == "warning"
    assert "also defined" in loc.message


def test_parse_split_ghdl_style_with_default_path():
    header = parse_ghdl_file_header(
        "Error: /mnt/c/Users/me/GHDL-STUDIO/examples/counter/counter.vhd:"
    )
    assert header == "/mnt/c/Users/me/GHDL-STUDIO/examples/counter/counter.vhd"
    loc = parse_ghdl_location(
        'Error: 24:31:error: missing ";" at end of statement',
        default_path=header,
    )
    assert loc == GhdlLocation(
        path=header,
        line=24,
        column=31,
        severity="error",
        message='missing ";" at end of statement',
    )


def test_parse_line_only_without_default_path_is_none():
    assert parse_ghdl_location("Error: 24:31:error: missing semicolon") is None


def test_parse_ignores_tool_only_errors():
    assert parse_ghdl_location("ghdl:error: cannot open bad.vhd") is None
    assert parse_ghdl_location("/usr/bin/ghdl-mcode:error: boom") is None
    assert parse_ghdl_location("./variabledelaytb:error: simulation failed") is None


def test_parse_ignores_non_diagnostic_lines():
    assert parse_ghdl_location("Analyze finished") is None
    assert parse_ghdl_location("%% Log PASSED") is None


def test_resolve_absolute_and_relative(tmp_path):
    src = tmp_path / "rtl" / "foo.vhd"
    src.parent.mkdir()
    src.write_text("entity foo is end;")
    assert resolve_ghdl_location_path(str(src)) == str(src.resolve())
    assert resolve_ghdl_location_path(
        "foo.vhd",
        search_roots=[str(tmp_path / "rtl")],
    ) == str(src.resolve())
    assert resolve_ghdl_location_path(
        "foo.vhd",
        known_files=[str(src)],
    ) == str(src.resolve())
    assert resolve_ghdl_location_path("missing.vhd", search_roots=[str(tmp_path)]) is None
