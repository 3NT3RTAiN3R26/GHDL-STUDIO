from ghdl_gui.vhdl_scanner import (
    find_verilog_modules,
    find_vhdl_entities,
    is_verilog_file,
    is_vhdl_file,
)

VHDL_SOURCE = """
library ieee;
use ieee.std_logic_1164.all;

entity counter is
    generic (WIDTH : integer := 4);
    port (clk : in std_logic);
end entity counter;

architecture rtl of counter is
begin
end architecture rtl;
"""

VHDL_TESTBENCH_SOURCE = """
entity counter_tb is
end entity counter_tb;

architecture sim of counter_tb is
begin
    dut : entity work.counter
        port map (clk => clk);
end architecture sim;
"""

VERILOG_SOURCE = """
module adder(input a, input b, output sum);
    assign sum = a ^ b;
endmodule

module top_level;
endmodule
"""


def test_is_vhdl_file():
    assert is_vhdl_file("foo.vhd")
    assert is_vhdl_file("foo.VHDL")
    assert not is_vhdl_file("foo.v")


def test_is_verilog_file():
    assert is_verilog_file("foo.v")
    assert is_verilog_file("foo.sv")
    assert not is_verilog_file("foo.vhd")


def test_find_vhdl_entities(tmp_path):
    counter_path = tmp_path / "counter.vhd"
    counter_path.write_text(VHDL_SOURCE, encoding="utf-8")
    tb_path = tmp_path / "counter_tb.vhd"
    tb_path.write_text(VHDL_TESTBENCH_SOURCE, encoding="utf-8")
    verilog_path = tmp_path / "adder.v"
    verilog_path.write_text(VERILOG_SOURCE, encoding="utf-8")

    entities = find_vhdl_entities([str(counter_path), str(tb_path), str(verilog_path)])
    assert entities == ["counter", "counter_tb"]


def test_find_vhdl_entities_ignores_non_vhdl_files(tmp_path):
    verilog_path = tmp_path / "adder.v"
    verilog_path.write_text(VERILOG_SOURCE, encoding="utf-8")
    assert find_vhdl_entities([str(verilog_path)]) == []


def test_find_vhdl_entities_deduplicates_case_insensitively(tmp_path):
    path = tmp_path / "dup.vhd"
    path.write_text("entity Foo is\nend entity Foo;\nentity foo is\nend entity foo;\n", encoding="utf-8")
    assert find_vhdl_entities([str(path)]) == ["Foo"]


def test_find_verilog_modules(tmp_path):
    verilog_path = tmp_path / "adder.v"
    verilog_path.write_text(VERILOG_SOURCE, encoding="utf-8")
    vhdl_path = tmp_path / "counter.vhd"
    vhdl_path.write_text(VHDL_SOURCE, encoding="utf-8")

    modules = find_verilog_modules([str(verilog_path), str(vhdl_path)])
    assert modules == ["adder", "top_level"]


def test_find_vhdl_entities_missing_file_is_ignored(tmp_path):
    missing = tmp_path / "does_not_exist.vhd"
    assert find_vhdl_entities([str(missing)]) == []
