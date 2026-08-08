from ghdl_gui.vcd_parser import parse_vcd_text

SAMPLE_VCD = """\
$date
   2026-08-08
$end
$version
   GHDL 4.1.0
$end
$timescale
   1 ns
$end
$scope module counter_tb $end
$var wire 1 ! clk $end
$var wire 4 " count $end
$upscope $end
$enddefinitions $end
#0
0!
b0000 "
#5
1!
#10
0!
b0001 "
#15
1!
"""


def test_parse_vcd_signals():
    data = parse_vcd_text(SAMPLE_VCD)
    assert set(data.signals.keys()) == {"!", '"'}
    clk_signal = data.signals["!"]
    assert clk_signal.name == "clk"
    assert clk_signal.size == 1
    assert clk_signal.scope == "counter_tb"


def test_parse_vcd_changes():
    data = parse_vcd_text(SAMPLE_VCD)
    assert data.changes["!"] == [(0, "0"), (5, "1"), (10, "0"), (15, "1")]
    assert data.changes['"'] == [(0, "0000"), (10, "0001")]
    assert data.end_time == 15


def test_parse_vcd_timescale():
    data = parse_vcd_text(SAMPLE_VCD)
    assert data.timescale == "1 ns"
