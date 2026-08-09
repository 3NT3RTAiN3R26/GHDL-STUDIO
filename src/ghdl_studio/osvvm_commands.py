"""OSVVM Scripts (.pro) helpers — Qt-free and unit-testable.

OSVVM project scripts (``.pro``) are TCL that use the OSVVM API after
``source …/Scripts/StartUp.tcl``. Typical batch flow::

    tclsh
    source /path/to/OsvvmLibraries/Scripts/StartUp.tcl
    build /path/to/project.pro
    exit

See https://github.com/OSVVM/OSVVM-Scripts
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

MODE_NORMAL = "normal"
MODE_OSVVM = "osvvm"
STUDIO_MODES = (MODE_NORMAL, MODE_OSVVM)

STARTUP_TCL_NAME = "StartUp.tcl"

# Default HTML report path relative to the directory that contains the .pro
# file (common OSVVM project layout). Override in Settings.
DEFAULT_OSVVM_HTML_REPORT = "build/build_all/build_all.html"

# Tried (in order) when the configured path is missing and still the default.
OSVVM_HTML_REPORT_FALLBACKS = (
    "build/build_all/build_all.html",
    "build_all/build_all.html",
    "index.html",
)


def find_tclsh_executable() -> str | None:
    """Return the path to ``tclsh`` (or ``tclsh86`` / ``tclsh8.6``) if on PATH."""
    for name in ("tclsh", "tclsh8.6", "tclsh86", "tclsh8.5"):
        found = shutil.which(name)
        if found:
            return found
    return None


def tcl_quote(path: str) -> str:
    """Quote a filesystem path for safe use inside a TCL script."""
    normalised = path.replace("\\", "/")
    escaped = normalised.replace("{", "\\{").replace("}", "\\}")
    return "{" + escaped + "}"


def resolve_startup_tcl(scripts_or_libraries_path: str) -> Path | None:
    """Locate ``StartUp.tcl`` under an OSVVM Scripts or OsvvmLibraries path.

    Accepts either the ``Scripts`` directory itself or the parent
    ``OsvvmLibraries`` (or similar) root that contains ``Scripts/StartUp.tcl``.
    """
    raw = (scripts_or_libraries_path or "").strip()
    if not raw:
        return None
    base = Path(raw).expanduser()
    candidates = [
        base / STARTUP_TCL_NAME,
        base / "Scripts" / STARTUP_TCL_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def is_pro_file(path: str) -> bool:
    """Return True for OSVVM project script files (``.pro``)."""
    return Path(path).suffix.lower() == ".pro"


def resolve_osvvm_html_report(
    pro_file: str,
    report_path: str | None = None,
) -> Path:
    """Resolve the OSVVM HTML report path for a ``.pro`` session.

    Relative ``report_path`` values are resolved against the directory that
    contains ``pro_file``. Absolute paths are returned as-is. Empty
    ``report_path`` uses :data:`DEFAULT_OSVVM_HTML_REPORT`.

    When the configured path does not exist and is still the default, common
    alternate layouts (``build_all/…``, ``index.html``) next to the ``.pro``
    are tried.
    """
    configured = (report_path or "").strip() or DEFAULT_OSVVM_HTML_REPORT
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    base = Path(pro_file).expanduser().resolve().parent
    primary = (base / candidate).resolve()
    if primary.is_file():
        return primary

    # Only search fallbacks when the user left the default / empty setting.
    using_default = not (report_path or "").strip() or configured in OSVVM_HTML_REPORT_FALLBACKS
    if using_default:
        for relative in OSVVM_HTML_REPORT_FALLBACKS:
            alt = (base / relative).resolve()
            if alt.is_file():
                return alt
    return primary


def ghdl_bin_directory(ghdl_executable: str | None) -> str | None:
    """Return the directory containing the configured GHDL executable, if any.

    Backslashes are normalised so Windows paths from Settings stay valid when
    quoted into TCL (and so unit tests on POSIX can assert on ``C:/…`` forms).
    """
    raw = (ghdl_executable or "").strip()
    if not raw:
        return None
    path = Path(raw.replace("\\", "/")).expanduser()
    if path.is_dir():
        try:
            return str(path.resolve()).replace("\\", "/")
        except OSError:
            return str(path).replace("\\", "/")
    parent = path.parent
    if str(parent) in ("", "."):
        return None
    try:
        if path.is_absolute():
            return str(parent.resolve()).replace("\\", "/")
    except OSError:
        pass
    return str(parent).replace("\\", "/")


def build_osvvm_env_bootstrap(ghdl_executable: str | None = None) -> str:
    """Return TCL that prepares PATH before ``source StartUp.tcl``.

    OSVVM ``VendorScripts_GHDL.tcl`` runs ``exec which ghdl``. Native Windows
    has no ``which`` command, so we install a tiny ``which.cmd`` shim that wraps
    ``where``. The Settings GHDL directory is prepended to ``PATH`` on all
    platforms so OSVVM finds the same GHDL the GUI uses.
    """
    bin_dir = ghdl_bin_directory(ghdl_executable)
    ghdl_dir_tcl = tcl_quote(bin_dir) if bin_dir else '""'
    return f"""# GHDL Studio: PATH + Windows `which` shim for OSVVM VendorScripts_GHDL.tcl
set _gsGhdlDir {ghdl_dir_tcl}
set _gsPrepend ""
if {{$::tcl_platform(platform) eq "windows"}} {{
  set _gsTemp ""
  if {{[info exists ::env(TEMP)] && $::env(TEMP) ne ""}} {{
    set _gsTemp $::env(TEMP)
  }} elseif {{[info exists ::env(TMP)] && $::env(TMP) ne ""}} {{
    set _gsTemp $::env(TMP)
  }} else {{
    set _gsTemp [pwd]
  }}
  set _gsShim [file normalize [file join $_gsTemp ghdl_studio_which_shim]]
  file mkdir $_gsShim
  set _gsCmd [file join $_gsShim which.cmd]
  set _gsFh [open $_gsCmd w]
  puts $_gsFh "@echo off"
  puts $_gsFh "where %*"
  close $_gsFh
  set _gsPrepend $_gsShim
  puts "GHDL Studio: installed Windows which.cmd shim in $_gsShim"
}}
if {{$_gsGhdlDir ne ""}} {{
  if {{$_gsPrepend ne ""}} {{
    if {{$::tcl_platform(platform) eq "windows"}} {{
      set _gsPrepend "$_gsGhdlDir;$_gsPrepend"
    }} else {{
      set _gsPrepend "$_gsGhdlDir:$_gsPrepend"
    }}
  }} else {{
    set _gsPrepend $_gsGhdlDir
  }}
  puts "GHDL Studio: prepended GHDL directory to PATH: $_gsGhdlDir"
}}
if {{$_gsPrepend ne ""}} {{
  if {{$::tcl_platform(platform) eq "windows"}} {{
    set ::env(PATH) "$_gsPrepend;$::env(PATH)"
  }} else {{
    set ::env(PATH) "$_gsPrepend:$::env(PATH)"
  }}
}}
"""


def build_osvvm_batch_script(
    startup_tcl: str,
    pro_file: str,
    *,
    ghdl_executable: str | None = None,
) -> str:
    """Return TCL source that loads OSVVM Scripts and builds a ``.pro`` file.

    ``build`` may raise after a successful simulate when HTML/YAML index
    reports fail (OSVVM Scripts quirk, e.g. missing dict key ``Passed``).
    This wrapper treats analyze/simulate error counts as the real status and
    exits 0 when those are zero so GHDL Studio can open waveforms.
    """
    if not startup_tcl:
        raise ValueError("OSVVM StartUp.tcl path is required.")
    if not pro_file:
        raise ValueError("A .pro file path is required.")
    bootstrap = build_osvvm_env_bootstrap(ghdl_executable)
    startup_q = tcl_quote(str(Path(startup_tcl).resolve()))
    pro_q = tcl_quote(str(Path(pro_file).resolve()))
    return f"""# Generated by GHDL Studio — do not edit
{bootstrap}source {startup_q}
# Do not fail the process solely because HTML/YAML reports misbehave.
if {{[info exists ::osvvm::FailOnReportErrors]}} {{
  set ::osvvm::FailOnReportErrors false
}}
set _ghdlStudioBuildRc [catch {{build {pro_q}}} _ghdlStudioBuildMsg]
set _ghdlStudioAnalyzeErr 0
set _ghdlStudioSimulateErr 0
if {{[info exists ::osvvm::AnalyzeErrorCount]}} {{
  set _ghdlStudioAnalyzeErr $::osvvm::AnalyzeErrorCount
}}
if {{[info exists ::osvvm::SimulateErrorCount]}} {{
  set _ghdlStudioSimulateErr $::osvvm::SimulateErrorCount
}}
if {{[info exists ::osvvm::BuildStatus]}} {{
  puts "GHDL Studio: BuildStatus=$::osvvm::BuildStatus AnalyzeErrors=$_ghdlStudioAnalyzeErr SimulateErrors=$_ghdlStudioSimulateErr"
}}
if {{$_ghdlStudioAnalyzeErr > 0 || $_ghdlStudioSimulateErr > 0}} {{
  puts "GHDL Studio: build failed (analyze/simulate errors)."
  if {{$_ghdlStudioBuildRc}} {{
    puts $_ghdlStudioBuildMsg
  }}
  exit 1
}}
if {{$_ghdlStudioBuildRc}} {{
  puts "GHDL Studio: analyze/simulate OK; ignoring post-build report error:"
  puts $_ghdlStudioBuildMsg
}}
exit 0
"""


@dataclass(frozen=True)
class OsvvmRunPlan:
    """Everything needed to launch ``tclsh`` for an OSVVM ``.pro`` build."""

    tclsh: str
    script_path: str
    cwd: str
    command_display: str


def prepare_osvvm_run(
    *,
    tclsh: str,
    startup_tcl: str,
    pro_file: str,
    script_dir: str | None = None,
    ghdl_executable: str | None = None,
) -> OsvvmRunPlan:
    """Write a temporary batch TCL script and return the run plan.

    ``cwd`` is the directory containing the ``.pro`` file so relative includes
    and GHDL work directories behave like a manual OSVVM Scripts session.

    ``ghdl_executable`` (optional) is the Settings GHDL path; its directory is
    prepended to ``PATH`` inside the batch script, and on Windows a ``which``
    shim is installed so OSVVM's VendorScripts can locate GHDL.
    """
    pro_path = Path(pro_file).resolve()
    if not pro_path.is_file():
        raise FileNotFoundError(f".pro file not found: {pro_file}")
    startup = Path(startup_tcl).resolve()
    if not startup.is_file():
        raise FileNotFoundError(f"StartUp.tcl not found: {startup_tcl}")
    if not tclsh:
        raise ValueError("tclsh executable is required.")

    content = build_osvvm_batch_script(
        str(startup),
        str(pro_path),
        ghdl_executable=ghdl_executable,
    )
    directory = script_dir or tempfile.gettempdir()
    Path(directory).mkdir(parents=True, exist_ok=True)
    script_file = Path(directory) / "ghdl_studio_osvvm_run.tcl"
    script_file.write_text(content, encoding="utf-8")

    return OsvvmRunPlan(
        tclsh=tclsh,
        script_path=str(script_file.resolve()),
        cwd=str(pro_path.parent),
        command_display=f"{tclsh} {script_file.resolve()}  # build {pro_path.name}",
    )


def find_recent_waveform(
    search_root: str,
    *,
    newer_than_mtime: float | None = None,
) -> str | None:
    """Find the newest ``.ghw`` / ``.vcd`` under ``search_root`` (shallow walk).

    Prefers ``.ghw`` when timestamps are equal. Used after an OSVVM ``build``
    to open waveforms in Surfer / the internal viewer when present.
    """
    root = Path(search_root)
    if not root.is_dir():
        return None

    best: Path | None = None
    best_mtime = -1.0
    for pattern in ("**/*.ghw", "**/*.vcd"):
        for candidate in root.glob(pattern):
            if not candidate.is_file():
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                continue
            if newer_than_mtime is not None and mtime < newer_than_mtime:
                continue
            if mtime > best_mtime or (
                mtime == best_mtime
                and best is not None
                and candidate.suffix.lower() == ".ghw"
                and best.suffix.lower() != ".ghw"
            ):
                best = candidate
                best_mtime = mtime
    return str(best.resolve()) if best is not None else None
