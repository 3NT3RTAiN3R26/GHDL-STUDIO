"""Tests for shipped example discovery."""

from pathlib import Path
import sys

from ghdl_studio.examples_catalog import (
    adder_normal_example,
    adder_osvvm_example,
    counter_example,
    find_examples_root,
)
from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM


def test_find_examples_root_from_repo():
    root = find_examples_root()
    assert root is not None
    assert (root / "counter" / "counter.vhd").is_file()
    assert (root / "adder" / "adder.pro").is_file()


def test_find_examples_root_next_to_frozen_exe(tmp_path, monkeypatch):
    """Portable builds ship examples/ beside GHDL-Studio.exe."""
    exe_dir = tmp_path / "GHDL-Studio"
    examples = exe_dir / "examples"
    counter = examples / "counter"
    counter.mkdir(parents=True)
    (counter / "counter.vhd").write_text("-- stub\n", encoding="utf-8")
    fake_exe = exe_dir / "GHDL-Studio.exe"
    fake_exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    monkeypatch.delenv("GHDL_STUDIO_EXAMPLES", raising=False)

    root = find_examples_root()
    assert root == examples.resolve()


def test_counter_and_adder_specs():
    counter = counter_example()
    assert counter is not None
    assert counter.mode == MODE_NORMAL
    assert counter.top_unit == "counter_tb"
    assert all(Path(p).is_file() for p in counter.files)

    adder_n = adder_normal_example()
    assert adder_n is not None
    assert adder_n.mode == MODE_NORMAL
    assert adder_n.top_unit == "adder_tb"

    adder_o = adder_osvvm_example()
    assert adder_o is not None
    assert adder_o.mode == MODE_OSVVM
    assert Path(adder_o.active_pro).name == "adder.pro"
