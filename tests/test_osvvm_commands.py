from pathlib import Path

import pytest

from ghdl_studio.osvvm_commands import (
    DEFAULT_OSVVM_HTML_REPORT,
    MODE_NORMAL,
    MODE_OSVVM,
    PRECOMPILE_ALL,
    PRECOMPILE_OSVVM,
    STUDIO_MODES,
    build_osvvm_batch_script,
    build_osvvm_env_bootstrap,
    build_osvvm_mcode_coverage_guard_tcl,
    build_osvvm_precompile_script,
    diagnose_osvvm_randompkg,
    find_compiled_ghdl_lib_dir,
    find_recent_waveform,
    ghdl_bin_directory,
    install_windows_osvvm_shims,
    is_pro_file,
    osvvm_library_has_randompkg,
    prepare_osvvm_precompile_run,
    prepare_osvvm_run,
    resolve_ghdl_executable_path,
    resolve_osvvm_home_directory,
    resolve_osvvm_html_report,
    resolve_osvvm_precompile_target,
    resolve_startup_tcl,
    tcl_quote,
)


def test_studio_modes_constants():
    assert MODE_NORMAL in STUDIO_MODES
    assert MODE_OSVVM in STUDIO_MODES


def test_is_pro_file():
    assert is_pro_file("runAll.pro")
    assert is_pro_file("path/to/Tb.PRO")
    assert not is_pro_file("run.tcl")
    assert not is_pro_file("top.vhd")


def test_tcl_quote_normalises_separators():
    assert tcl_quote(r"C:\Osvvm\Scripts\StartUp.tcl") == "{C:/Osvvm/Scripts/StartUp.tcl}"
    assert tcl_quote("/tmp/a b/file.pro") == "{/tmp/a b/file.pro}"


def test_resolve_startup_tcl_scripts_dir(tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    startup = scripts / "StartUp.tcl"
    startup.write_text("# osvvm\n", encoding="utf-8")
    assert resolve_startup_tcl(str(scripts)) == startup.resolve()
    assert resolve_startup_tcl(str(tmp_path)) == startup.resolve()
    assert resolve_startup_tcl(str(tmp_path / "missing")) is None


def test_ghdl_bin_directory():
    assert ghdl_bin_directory(None) is None
    assert ghdl_bin_directory("") is None
    assert ghdl_bin_directory(r"C:\tools\ghdl\bin\ghdl.exe") == "C:/tools/ghdl/bin"
    assert ghdl_bin_directory("C:/tools/ghdl/bin/ghdl.exe") == "C:/tools/ghdl/bin"
    assert ghdl_bin_directory("/opt/ghdl/bin/ghdl").replace("\\", "/").endswith("/opt/ghdl/bin")


def test_resolve_ghdl_executable_path_prefers_exe(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    plain = bin_dir / "ghdl"
    exe = bin_dir / "ghdl.exe"
    plain.write_text("x", encoding="utf-8")
    exe.write_text("y", encoding="utf-8")
    assert resolve_ghdl_executable_path(str(plain)).endswith("ghdl.exe")
    assert resolve_ghdl_executable_path(str(bin_dir)).endswith("ghdl.exe")
    assert resolve_ghdl_executable_path(r"C:\Program Files (x86)\Ghdl\bin\ghdl") == (
        "C:/Program Files (x86)/Ghdl/bin/ghdl.exe"
    )


def test_install_windows_osvvm_shims_single_path_and_quoted_target(tmp_path):
    target = r"C:\Program Files (x86)\Ghdl\bin\ghdl.exe"
    shim = install_windows_osvvm_shims(tmp_path / "shim", target)
    which_body = (shim / "which.cmd").read_text(encoding="utf-8")
    assert "for /f" in which_body
    assert "exit /b 0" in which_body
    assert "where %*" in which_body
    # Must not dump every `where` match (OSVVM execs the whole string).
    assert which_body.count("where %*") == 1
    ghdl_cmd = (shim / "ghdl.cmd").read_text(encoding="utf-8")
    assert '"C:\\Program Files (x86)\\Ghdl\\bin\\ghdl.exe"' in ghdl_cmd
    assert "%*" in ghdl_cmd


def test_build_osvvm_env_bootstrap_windows_which_shim_and_path(tmp_path):
    shim = tmp_path / "ghdl_studio_which_shim"
    shim.mkdir()
    bootstrap = build_osvvm_env_bootstrap(
        r"C:\ghdl\bin\ghdl.exe",
        windows_shim_dir=str(shim),
    )
    assert 'tcl_platform(platform) eq "windows"' in bootstrap
    assert "ghdl_studio_which_shim" in bootstrap.replace("\\", "/")
    assert "C:/ghdl/bin" in bootstrap.replace("\\", "/")
    assert 'set ::env(PATH)' in bootstrap
    # Shim dir must be prepended before the real GHDL dir.
    assert bootstrap.index("_gsShimDir") < bootstrap.index("set ::env(PATH)")


def test_mcode_coverage_guard_wraps_set_coverage():
    guard = build_osvvm_mcode_coverage_guard_tcl()
    assert "mcode" in guard
    assert "SetCoverageSimulateEnable" in guard
    assert "SetCoverageAnalyzeEnable" in guard
    assert "GHDL_STUDIO_OSVVM_COVERAGE" in guard
    assert "wrapCoverageOff" not in guard


def test_osvvm_library_has_randompkg(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not osvvm_library_has_randompkg(empty)
    compiled = tmp_path / "VHDL_LIBS" / "GHDL-6.0.0"
    (compiled / "osvvm" / "v08").mkdir(parents=True)
    (compiled / "osvvm" / "osvvm-obj08.cf").write_text("x", encoding="utf-8")
    assert osvvm_library_has_randompkg(compiled)


def test_diagnose_osvvm_randompkg_warns_when_empty(tmp_path):
    pro = tmp_path / "build" / "all.pro"
    pro.parent.mkdir()
    pro.write_text("build\n", encoding="utf-8")
    lib = tmp_path / "osvvm_ghdl" / "VHDL_LIBS" / "GHDL-6.0.0"
    lib.mkdir(parents=True)
    warnings = diagnose_osvvm_randompkg(str(pro), osvvm_lib_path=str(lib))
    assert warnings
    assert "randompkg" in warnings[0].lower()


def test_build_osvvm_batch_script_contains_source_and_build(tmp_path):
    startup = tmp_path / "StartUp.tcl"
    startup.write_text("#\n", encoding="utf-8")
    pro = tmp_path / "demo.pro"
    pro.write_text("analyze a.vhd\n", encoding="utf-8")
    shim = tmp_path / "shim"
    shim.mkdir()
    script = build_osvvm_batch_script(
        str(startup),
        str(pro),
        windows_shim_dir=str(shim),
    )
    assert "source {" in script
    assert "StartUp.tcl}" in script
    assert "build {" in script
    assert "demo.pro}" in script
    # Windows shim PATH setup must run before StartUp.tcl (VendorScripts_GHDL).
    assert script.index("_gsShimDir") < script.index("source {")
    # Coverage guard runs after StartUp so SetCoverage* APIs exist.
    assert script.index("source {") < script.index("GHDL_STUDIO_OSVVM_COVERAGE")
    assert script.index("GHDL_STUDIO_OSVVM_COVERAGE") < script.index("catch {build")
    # Wrapper must tolerate OSVVM report failures after a PASSED simulate.
    assert "catch {build" in script
    assert "AnalyzeErrorCount" in script
    assert "SimulateErrorCount" in script
    assert script.strip().endswith("exit 0")


def test_prepare_osvvm_run_writes_batch_script(tmp_path):
    startup = tmp_path / "StartUp.tcl"
    startup.write_text("#\n", encoding="utf-8")
    pro = tmp_path / "proj" / "run.pro"
    pro.parent.mkdir()
    pro.write_text("simulate tb\n", encoding="utf-8")
    ghdl = tmp_path / "ghdl-bin" / "ghdl"
    ghdl.parent.mkdir()
    ghdl.write_text("#!/bin/sh\n", encoding="utf-8")
    plan = prepare_osvvm_run(
        tclsh="/usr/bin/tclsh",
        startup_tcl=str(startup),
        pro_file=str(pro),
        script_dir=str(tmp_path / "tmp"),
        ghdl_executable=str(ghdl),
    )
    assert plan.tclsh == "/usr/bin/tclsh"
    assert plan.cwd == str(pro.parent.resolve())
    assert Path(plan.script_path).is_file()
    text = Path(plan.script_path).read_text(encoding="utf-8")
    assert "source" in text and "build" in text
    assert "ghdl_studio_which_shim" in text.replace("\\", "/")
    assert "ghdl-bin" in text.replace("\\", "/")
    shim = Path(plan.script_path).parent / "ghdl_studio_which_shim"
    assert (shim / "which.cmd").is_file()
    assert (shim / "ghdl.cmd").is_file()
    ghdl_cmd = (shim / "ghdl.cmd").read_text(encoding="utf-8")
    assert "ghdl-bin" in ghdl_cmd.replace("\\", "/")
    assert ghdl_cmd.strip().startswith("@echo off")


def _fake_osvvm_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal OsvvmLibraries layout with Scripts/StartUp.tcl + osvvm/."""
    home = tmp_path / "OsvvmLibraries"
    scripts = home / "Scripts"
    scripts.mkdir(parents=True)
    startup = scripts / "StartUp.tcl"
    startup.write_text("# fake startup\n", encoding="utf-8")
    util = home / "osvvm"
    util.mkdir()
    (util / "osvvm.pro").write_text("library osvvm\n", encoding="utf-8")
    (home / "OsvvmLibraries.pro").write_text("include ./osvvm\n", encoding="utf-8")
    return home, startup


def test_resolve_osvvm_home_and_precompile_target(tmp_path):
    home, startup = _fake_osvvm_tree(tmp_path)
    assert resolve_osvvm_home_directory(str(startup)) == home.resolve()
    assert resolve_osvvm_home_directory(str(home / "Scripts")) == home.resolve()
    assert resolve_osvvm_home_directory(str(home)) == home.resolve()
    assert resolve_osvvm_precompile_target(home, PRECOMPILE_OSVVM) == (home / "osvvm").resolve()
    assert resolve_osvvm_precompile_target(home, PRECOMPILE_ALL) == (
        home / "OsvvmLibraries.pro"
    ).resolve()
    with pytest.raises(FileNotFoundError):
        resolve_osvvm_precompile_target(tmp_path / "empty", PRECOMPILE_OSVVM)


def test_find_compiled_ghdl_lib_dir(tmp_path):
    root = tmp_path / "osvvm_ghdl"
    ghdl_lib = root / "VHDL_LIBS" / "GHDL-6.0.0"
    (ghdl_lib / "osvvm").mkdir(parents=True)
    assert find_compiled_ghdl_lib_dir(str(root)) == ghdl_lib.resolve()
    assert find_compiled_ghdl_lib_dir(str(ghdl_lib)) == ghdl_lib.resolve()
    assert find_compiled_ghdl_lib_dir(str(root / "VHDL_LIBS")) == ghdl_lib.resolve()
    assert find_compiled_ghdl_lib_dir(str(tmp_path / "missing")) is None


def test_find_compiled_ghdl_lib_dir_prefers_matching_version(tmp_path, monkeypatch):
    root = tmp_path / "osvvm_ghdl"
    older = root / "VHDL_LIBS" / "GHDL-4.1.0"
    newer = root / "VHDL_LIBS" / "GHDL-6.0.0"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    # Make the older tree look "newer" by mtime so version match must win.
    import os
    import time

    now = time.time()
    os.utime(newer, (now - 100, now - 100))
    os.utime(older, (now, now))

    ghdl = tmp_path / "ghdl"
    ghdl.write_text("#!/bin/sh\necho 'GHDL 6.0.0'\n", encoding="utf-8")
    ghdl.chmod(0o755)

    from ghdl_studio import osvvm_commands as oc

    monkeypatch.setattr(oc, "get_ghdl_version", lambda _bin: "6.0.0")
    assert find_compiled_ghdl_lib_dir(str(root), ghdl_bin=str(ghdl)) == newer.resolve()


def test_build_osvvm_precompile_script(tmp_path):
    home, startup = _fake_osvvm_tree(tmp_path)
    lib_dir = tmp_path / "osvvm_ghdl"
    lib_dir.mkdir()
    script = build_osvvm_precompile_script(
        str(startup),
        library_directory=str(lib_dir),
        target=PRECOMPILE_OSVVM,
    )
    assert "SetLibraryDirectory" in script
    assert "build {" in script
    assert "osvvm}" in script.replace("\\", "/")
    assert script.index("SetLibraryDirectory") < script.index("build {")
    assert "source {" in script


def test_prepare_osvvm_precompile_run(tmp_path):
    home, startup = _fake_osvvm_tree(tmp_path)
    lib_dir = tmp_path / "libs"
    plan = prepare_osvvm_precompile_run(
        tclsh="/usr/bin/tclsh",
        startup_tcl=str(startup),
        library_directory=str(lib_dir),
        target=PRECOMPILE_OSVVM,
        script_dir=str(tmp_path / "tmp"),
        ghdl_executable=str(tmp_path / "bin" / "ghdl"),
    )
    assert plan.cwd == str(lib_dir.resolve())
    assert Path(plan.script_path).name == "ghdl_studio_osvvm_precompile.tcl"
    text = Path(plan.script_path).read_text(encoding="utf-8")
    assert "SetLibraryDirectory" in text
    assert "precompile" in plan.command_display.lower()
    assert home.name in text or "osvvm" in text


def test_resolve_osvvm_html_report_default_relative(tmp_path):
    pro = tmp_path / "proj" / "run.pro"
    pro.parent.mkdir()
    pro.write_text("#\n", encoding="utf-8")
    resolved = resolve_osvvm_html_report(str(pro))
    assert resolved == (pro.parent / DEFAULT_OSVVM_HTML_REPORT).resolve()
    assert DEFAULT_OSVVM_HTML_REPORT == "build/build_all/build_all.html"


def test_resolve_osvvm_html_report_custom_and_absolute(tmp_path):
    pro = tmp_path / "run.pro"
    pro.write_text("#\n", encoding="utf-8")
    relative = resolve_osvvm_html_report(str(pro), "reports/summary.html")
    assert relative == (tmp_path / "reports" / "summary.html").resolve()
    absolute = tmp_path / "elsewhere" / "out.html"
    resolved_abs = resolve_osvvm_html_report(str(pro), str(absolute))
    assert resolved_abs == absolute.resolve()


def test_resolve_osvvm_html_report_fallback_build_all(tmp_path):
    """If default build/… is missing, fall back to build_all/build_all.html."""
    pro = tmp_path / "run.pro"
    pro.write_text("#\n", encoding="utf-8")
    legacy = tmp_path / "build_all" / "build_all.html"
    legacy.parent.mkdir()
    legacy.write_text("<html></html>", encoding="utf-8")
    resolved = resolve_osvvm_html_report(str(pro), "")
    assert resolved == legacy.resolve()


def test_find_recent_waveform_prefers_newest(tmp_path):
    older = tmp_path / "old.vcd"
    newer = tmp_path / "sim" / "new.ghw"
    newer.parent.mkdir()
    older.write_text("x", encoding="utf-8")
    newer.write_text("y", encoding="utf-8")
    # Ensure newer mtime
    import os
    import time

    past = time.time() - 100
    os.utime(older, (past, past))
    found = find_recent_waveform(str(tmp_path))
    assert found == str(newer.resolve())
