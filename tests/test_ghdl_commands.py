from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    RunOptions,
    build_analyze_args,
    build_clean_args,
    build_elaborate_args,
    build_library_search_args,
    build_run_args,
    build_simulation_option_args,
    clean_output_dir,
    elaborated_executable_path,
    ensure_osvvm_run_scaffold,
    parse_ghdl_version,
    stage_stimulus_files,
    stimulus_input_dir,
)


def test_build_analyze_args_basic():
    args = build_analyze_args(["counter.vhd", "counter_tb.vhd"])
    assert args == ["-a", "--std=08", "counter.vhd", "counter_tb.vhd"]


def test_build_clean_args_basic():
    assert build_clean_args() == ["--clean", "--std=08"]


def test_build_clean_args_with_workdir_and_libs():
    args = build_clean_args(
        std="08",
        work_dir="/tmp/out",
        library_paths=["/libs/osvvm", ""],
    )
    assert args == [
        "--clean",
        "--std=08",
        "--workdir=/tmp/out",
        "-P/libs/osvvm",
    ]


def test_build_analyze_args_with_workdir_and_extra():
    args = build_analyze_args(
        ["a.vhd"], std="93", work_dir="build", extra_args=["-fsynopsys"]
    )
    assert args == ["-a", "--std=93", "--workdir=build", "-fsynopsys", "a.vhd"]


def test_build_library_search_args_skips_empty():
    assert build_library_search_args("", "  ") == []
    assert build_library_search_args("/libs/osvvm", "", "/libs/custom") == [
        "-P/libs/osvvm",
        "-P/libs/custom",
    ]


def test_build_analyze_args_with_library_paths():
    args = build_analyze_args(
        ["a.vhd"],
        library_paths=["/opt/osvvm", "/home/me/libs"],
        extra_args=["-fsynopsys"],
    )
    assert args == [
        "-a",
        "--std=08",
        "-P/opt/osvvm",
        "-P/home/me/libs",
        "-fsynopsys",
        "a.vhd",
    ]


def test_build_elaborate_and_run_args_with_library_paths():
    elab = build_elaborate_args("tb", library_paths=["/opt/osvvm"])
    assert elab == ["-e", "--std=08", "-P/opt/osvvm", "tb"]
    run = build_run_args("tb", library_paths=["/opt/osvvm"], vcd_path="tb.vcd")
    assert run == ["-r", "--std=08", "-P/opt/osvvm", "tb", "--vcd=tb.vcd"]


def test_run_options_library_paths():
    options = RunOptions(osvvm_lib_path="/osvvm", custom_lib_path="/custom")
    assert options.library_paths() == ["/osvvm", "/custom"]


def test_elaborated_executable_path_finds_binary(tmp_path):
    binary = tmp_path / "variabledelaytb"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    assert elaborated_executable_path(str(tmp_path), "variabledelaytb") == str(binary.resolve())
    assert elaborated_executable_path(str(tmp_path), "missing") is None


def test_build_simulation_option_args():
    args = build_simulation_option_args(
        vcd_path="/tmp/a.vcd",
        wave_path="/tmp/a.ghw",
        stop_time="200ns",
        generics={"WIDTH": "8"},
    )
    assert args == [
        "-gWIDTH=8",
        "--vcd=/tmp/a.vcd",
        "--wave=/tmp/a.ghw",
        "--stop-time=200ns",
    ]


def test_ensure_osvvm_run_scaffold_creates_dir_and_executable_yml(tmp_path):
    yml = ensure_osvvm_run_scaffold(str(tmp_path))
    assert yml == tmp_path / "OsvvmTemp_GHDL" / "OsvvmRun.yml"
    assert yml.is_file()
    # Second call is idempotent and must not fail if the file already exists.
    again = ensure_osvvm_run_scaffold(str(tmp_path))
    assert again == yml
    assert yml.stat().st_mode & 0o111  # executable bit set on Unix


def test_stimulus_input_dir_is_sibling_of_output(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    assert stimulus_input_dir(str(output)) == (tmp_path / "input").resolve()


def test_stage_stimulus_files_copies_into_sibling_input(tmp_path):
    project = tmp_path / "trunk"
    output = project / "output"
    output.mkdir(parents=True)
    source = project / "stim" / "ref_wave_data.txt"
    source.parent.mkdir()
    source.write_text("1.0 2.0\n", encoding="utf-8")

    staged = stage_stimulus_files([str(source)], str(output))
    dest = project / "input" / "ref_wave_data.txt"
    assert dest.is_file()
    assert dest.read_text(encoding="utf-8") == "1.0 2.0\n"
    assert len(staged) == 1
    assert staged[0].action == "copied"
    assert staged[0].destination == str(dest.resolve())


def test_stage_stimulus_files_already_in_place(tmp_path):
    project = tmp_path / "trunk"
    output = project / "output"
    input_dir = project / "input"
    output.mkdir(parents=True)
    input_dir.mkdir()
    source = input_dir / "ref_wave_data.txt"
    source.write_text("x\n", encoding="utf-8")

    staged = stage_stimulus_files([str(source)], str(output))
    assert staged[0].action == "already_in_place"
    assert source.read_text(encoding="utf-8") == "x\n"


def test_stage_stimulus_files_reports_missing_source(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    missing = tmp_path / "gone.txt"
    staged = stage_stimulus_files([str(missing)], str(output))
    assert staged[0].action == "missing_source"
    assert not (tmp_path / "input" / "gone.txt").exists()


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
