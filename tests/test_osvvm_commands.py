from pathlib import Path

from ghdl_studio.osvvm_commands import (
    DEFAULT_OSVVM_HTML_REPORT,
    MODE_NORMAL,
    MODE_OSVVM,
    STUDIO_MODES,
    build_osvvm_batch_script,
    build_osvvm_env_bootstrap,
    find_recent_waveform,
    ghdl_bin_directory,
    install_windows_osvvm_shims,
    is_pro_file,
    prepare_osvvm_run,
    resolve_ghdl_executable_path,
    resolve_osvvm_html_report,
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
