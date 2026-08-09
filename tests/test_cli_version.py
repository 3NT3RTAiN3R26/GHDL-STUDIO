"""CLI ``--version`` / ``-V`` for ghdl-studio."""

import pytest

from ghdl_studio import __version__
from ghdl_studio.app import build_arg_parser


def test_package_version_is_0_5_2():
    assert __version__ == "0.5.2"


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
