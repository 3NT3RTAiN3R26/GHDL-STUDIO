from ghdl_studio.vcd_parser import (
    format_femtoseconds,
    format_raw_time,
    parse_timescale,
    parse_vcd_text,
    raw_time_to_femtoseconds,
)

# GHDL erzeugt $timescale mehrzeilig (Wert auf einer eigenen Zeile) und nutzt
# standardmaessig Femtosekunden. Bewusst NICHT "1 ns" (= Default-Wert von
# VcdData.timescale) verwendet, damit ein Regressionstest, der die
# Zeitbasis nicht korrekt aus der VCD-Datei ausliest, nicht durch Zufall
# gruen wird.
SAMPLE_VCD = """\
$date
   2026-08-08
$end
$version
   GHDL 4.1.0
$end
$timescale
   1 fs
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
    assert data.timescale == "1 fs"


def test_parse_vcd_timescale_single_line_format():
    single_line_vcd = SAMPLE_VCD.replace("$timescale\n   1 fs\n$end", "$timescale 1 fs $end")
    data = parse_vcd_text(single_line_vcd)
    assert data.timescale == "1 fs"


def test_parse_timescale_various_formats():
    assert parse_timescale("1 ns") == (1.0, "ns")
    assert parse_timescale("10ps") == (10.0, "ps")
    assert parse_timescale("1fs") == (1.0, "fs")
    assert parse_timescale("garbage") == (1.0, "ns")


def test_raw_time_to_femtoseconds():
    assert raw_time_to_femtoseconds(5, "1 ns") == 5_000_000
    assert raw_time_to_femtoseconds(5_000_000, "1 fs") == 5_000_000


def test_format_femtoseconds_chooses_readable_unit():
    assert format_femtoseconds(0) == "0 s"
    assert format_femtoseconds(5_000_000) == "5 ns"
    assert format_femtoseconds(1_500) == "1.5 ps"
    assert format_femtoseconds(200_000_000) == "200 ns"


def test_format_raw_time_uses_vcd_timescale():
    # 200 Ticks bei einer Femtosekunden-Zeitbasis von 1e6 fs/Tick (= 1 ns) ergeben 200 ns.
    assert format_raw_time(200, "1000000 fs") == "200 ns"
    assert format_raw_time(5, "1 ns") == "5 ns"
