from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    RunOptions,
    build_analyze_args,
    build_elaborate_args,
    build_run_args,
    clean_output_dir,
    parse_ghdl_version,
)


def test_build_analyze_args_basic():
    args = build_analyze_args(["counter.vhd", "counter_tb.vhd"])
    assert args == ["-a", "--std=08", "counter.vhd", "counter_tb.vhd"]


def test_build_analyze_args_with_workdir_and_extra():
    args = build_analyze_args(
        ["a.vhd"], std="93", work_dir="build", extra_args=["-fsynopsys"]
    )
    assert args == ["-a", "--std=93", "--workdir=build", "-fsynopsys", "a.vhd"]


def test_build_analyze_args_requires_files():
    try:
        build_analyze_args([])
    except ValueError:
        pass
    else:
        raise AssertionError("Expected a ValueError to be raised.")


def test_build_elaborate_args():
    args = build_elaborate_args("counter_tb", std="08")
    assert args == ["-e", "--std=08", "counter_tb"]


def test_build_run_args_with_vcd_and_generics():
    args = build_run_args(
        "counter_tb",
        std="08",
        vcd_path="out.vcd",
        wave_path="out.ghw",
        stop_time="200ns",
        generics={"WIDTH": "8"},
    )
    assert args == [
        "-r",
        "--std=08",
        "counter_tb",
        "-gWIDTH=8",
        "--vcd=out.vcd",
        "--wave=out.ghw",
        "--stop-time=200ns",
    ]


def test_parse_ghdl_version_typical_output():
    output = "GHDL 4.1.0 (2.0.0.r0.g...) [Dunoon edition]\n Compiled with GNAT Version: 12.2.0\n"
    info = parse_ghdl_version(output)
    assert info.version == "4.1.0"


def test_run_options_default_analyze_args_include_gcc_backend_flags():
    options = RunOptions()
    assert options.extra_analyze_args == list(DEFAULT_ANALYZE_EXTRA_ARGS)


def test_run_options_default_elaborate_args_include_gcc_backend_flags():
    options = RunOptions()
    assert options.extra_elaborate_args == list(DEFAULT_ELABORATE_EXTRA_ARGS)


def test_run_options_default_run_args_include_gcc_backend_flags():
    options = RunOptions()
    assert options.extra_run_args == list(DEFAULT_RUN_EXTRA_ARGS)


def test_build_analyze_args_with_default_gcc_backend_flags():
    args = build_analyze_args(
        ["counter.vhd"], extra_args=list(DEFAULT_ANALYZE_EXTRA_ARGS)
    )
    assert args == [
        "-a",
        "--std=08",
        "-Wc,-fprofile-arcs",
        "-Wc,-ftest-coverage",
        "-fsynopsys",
        "-fPIE",
        "counter.vhd",
    ]


def test_build_elaborate_args_with_default_gcc_backend_flags():
    args = build_elaborate_args(
        "counter_tb", extra_args=list(DEFAULT_ELABORATE_EXTRA_ARGS)
    )
    assert args == [
        "-e",
        "--std=08",
        "-Wl,-lgcov",
        "-fsynopsys",
        "-fPIE",
        "counter_tb",
    ]


def test_run_options_default_output_dir():
    options = RunOptions()
    assert options.output_dir == DEFAULT_OUTPUT_DIR == "output"


def test_run_options_vcd_filename_and_path():
    options = RunOptions(top_unit="counter_tb", output_dir="output")
    assert options.vcd_filename() == "counter_tb.vcd"
    assert options.vcd_path() == "output/counter_tb.vcd"
    assert options.ghw_filename() == "counter_tb.ghw"
    assert options.ghw_path() == "output/counter_tb.ghw"


def test_run_options_vcd_path_uses_custom_output_dir():
    options = RunOptions(top_unit="counter_tb", output_dir="my_build")
    assert options.vcd_path() == "my_build/counter_tb.vcd"
    assert options.ghw_path() == "my_build/counter_tb.ghw"


def test_clean_output_dir_removes_all_entries(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "counter_tb.vcd").write_text("dummy")
    (output_dir / "counter_tb.ghw").write_text("dummy")
    (output_dir / "counter_tb.o").write_text("dummy")
    (output_dir / "counter_tb.gcda").write_text("dummy")
    (output_dir / "counter_tb.gcno").write_text("dummy")
    (output_dir / "work-obj08.cf").write_text("dummy")
    (output_dir / "counter_tb").write_text("dummy")  # simulierte Executable
    sub_dir = output_dir / "some_subdir"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("dummy")

    removed = clean_output_dir(str(output_dir))

    assert output_dir.exists()  # Verzeichnis selbst bleibt bestehen
    assert list(output_dir.iterdir()) == []
    assert set(removed) == {
        "counter_tb.vcd",
        "counter_tb.ghw",
        "counter_tb.o",
        "counter_tb.gcda",
        "counter_tb.gcno",
        "work-obj08.cf",
        "counter_tb",
        "some_subdir",
    }


def test_clean_output_dir_nonexistent_directory_returns_empty(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert clean_output_dir(str(missing)) == []


def test_build_run_args_extra_args_precede_unit_name():
    # -fsynopsys ist eine allgemeine GHDL-Option und muss laut Syntax
    # "-r <[options...] unit [simulation_options...]>" VOR dem Unit-Namen
    # stehen, waehrend Generics/--vcd=/--wave=/--stop-time= DANACH folgen.
    args = build_run_args(
        "counter_tb",
        vcd_path="out.vcd",
        wave_path="out.ghw",
        stop_time="200ns",
        generics={"WIDTH": "8"},
        extra_args=list(DEFAULT_RUN_EXTRA_ARGS),
    )
    assert args == [
        "-r",
        "--std=08",
        "-fsynopsys",
        "counter_tb",
        "-gWIDTH=8",
        "--vcd=out.vcd",
        "--wave=out.ghw",
        "--stop-time=200ns",
    ]
