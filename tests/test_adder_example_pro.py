"""Sanity checks for the adder OSVVM example ``.pro`` script."""

from pathlib import Path

from ghdl_studio.osvvm_commands import build_osvvm_batch_script, is_pro_file

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDER_PRO = REPO_ROOT / "examples" / "adder" / "adder.pro"


def test_adder_pro_exists_and_is_recognised():
    assert ADDER_PRO.is_file()
    assert is_pro_file(str(ADDER_PRO))


def test_adder_pro_contains_analyze_and_simulate():
    text = ADDER_PRO.read_text(encoding="utf-8")
    assert "analyze adder.vhd" in text
    assert "analyze adder_tb.vhd" in text
    assert "simulate adder_tb" in text
    assert "SetSaveWaves" in text
    assert "SetVHDLVersion 2008" in text
    # Must pull in library osvvm before analyzing the OSVVM testbench.
    assert "include $_osvvmUtil" in text
    assert "OsvvmLibraries" in text
    assert "osvvm" in text


def test_adder_pro_can_be_wired_into_osvvm_batch(tmp_path):
    """Batch script builder accepts the example .pro path (no TCL required)."""
    startup = tmp_path / "StartUp.tcl"
    startup.write_text("# stub\n", encoding="utf-8")
    script = build_osvvm_batch_script(str(startup), str(ADDER_PRO))
    assert "adder.pro}" in script.replace("\\", "/")
    assert "build {" in script
