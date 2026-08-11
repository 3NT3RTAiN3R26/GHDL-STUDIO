"""Tests for GCC coverage artifact discovery."""

from ghdl_studio.ghdl_commands import find_coverage_artifacts, format_coverage_hint


def test_find_coverage_artifacts_empty(tmp_path):
    assert find_coverage_artifacts(str(tmp_path)) == []
    assert find_coverage_artifacts(str(tmp_path / "missing")) == []
    assert format_coverage_hint(str(tmp_path)) is None


def test_find_coverage_artifacts_and_hint(tmp_path):
    (tmp_path / "tb.gcno").write_text("x")
    (tmp_path / "tb.gcda").write_text("y")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "extra.gcno").write_text("z")

    found = find_coverage_artifacts(str(tmp_path))
    assert len(found) == 3
    assert all(p.endswith((".gcda", ".gcno")) for p in found)

    hint = format_coverage_hint(str(tmp_path), found)
    assert hint is not None
    assert str(tmp_path.resolve()) in hint or str(tmp_path) in hint
    assert ".gcno" in hint
    assert ".gcda" in hint
