"""CLI ``--version`` / ``-V`` for ghdl-studio."""

from pathlib import Path

import pytest

from ghdl_studio import __version__
from ghdl_studio.app import build_arg_parser


def test_package_version_matches_pyproject():
    """Keep ``__version__`` and ``pyproject.toml`` in lockstep."""
    text = Path(__file__).resolve().parents[1].joinpath("pyproject.toml").read_text(
        encoding="utf-8"
    )
    match = next(
        (line.split("=", 1)[1].strip().strip('"') for line in text.splitlines() if line.startswith("version =")),
        None,
    )
    assert match == __version__ == "0.9.0"


def test_version_flag_prints_and_exits(capsys):
    parser = build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--version"])
    assert exc.value.code == 0
    assert f"ghdl-studio {__version__}" in capsys.readouterr().out


def test_short_version_flag(capsys):
    parser = build_arg_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["-V"])
    assert exc.value.code == 0
    assert "ghdl-studio" in capsys.readouterr().out
