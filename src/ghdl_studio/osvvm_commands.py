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

from ghdl_studio.ghdl_commands import get_ghdl_version

MODE_NORMAL = "normal"
MODE_OSVVM = "osvvm"
STUDIO_MODES = (MODE_NORMAL, MODE_OSVVM)

# Precompile targets for Simulation → Precompile OSVVM library…
PRECOMPILE_OSVVM = "osvvm"
PRECOMPILE_ALL = "all"
PRECOMPILE_TARGETS = (PRECOMPILE_OSVVM, PRECOMPILE_ALL)

STARTUP_TCL_NAME = "StartUp.tcl"

# Default HTML report path relative to the directory that contains the .pro
# file (common OSVVM project layout). Override in Settings.
DEFAULT_OSVVM_HTML_REPORT = "build/build_all/build_all.html"

# Tried (in order) when the configured path is missing and still the default.
OSVVM_HTML_REPORT_FALLBACKS = (
    "build/build_all/build_all.html",
    "build_all/build_all.html",
    "build/build_all_windows/build_all_windows.html",
    "build_all_windows/build_all_windows.html",
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


def resolve_ghdl_executable_path(ghdl_executable: str | None) -> str | None:
    """Resolve a concrete GHDL binary path for OSVVM / Windows shims.

    Prefers Settings, then ``PATH``. On Windows, prefers ``ghdl.exe`` over an
    extensionless ``ghdl`` next to it (``where`` often lists both).
    """
    raw = (ghdl_executable or "").strip()
    if raw:
        path = Path(raw.replace("\\", "/")).expanduser()
        if path.is_dir():
            for name in ("ghdl.exe", "ghdl"):
                candidate = path / name
                if candidate.is_file():
                    return str(candidate.resolve()).replace("\\", "/")
            return None
        exe_sibling = Path(str(path) + ".exe") if path.suffix == "" else path.with_suffix(".exe")
        if path.suffix.lower() != ".exe" and exe_sibling.is_file():
            return str(exe_sibling.resolve()).replace("\\", "/")
        if path.is_file():
            return str(path.resolve()).replace("\\", "/")
        # Keep configured path even if missing (user machine / cross-OS tests).
        if path.suffix.lower() != ".exe" and path.suffix == "":
            return (str(path) + ".exe").replace("\\", "/")
        return str(path).replace("\\", "/")
    found = shutil.which("ghdl")
    return found.replace("\\", "/") if found else None


_WHICH_CMD_BODY = """@echo off
setlocal EnableExtensions
rem Unix `which` returns a single path. `where` prints every match; OSVVM then
rem does `exec $ghdl --version` and breaks on multi-line / spaced paths.
if /I "%~1"=="ghdl" if exist "%~dp0ghdl.cmd" (
  echo %~dp0ghdl.cmd
  exit /b 0
)
for /f "delims=" %%i in ('where %* 2^>nul') do (
  echo %%i
  exit /b 0
)
exit /b 1
"""


def install_windows_osvvm_shims(
    shim_dir: str | Path,
    ghdl_executable: str | None = None,
) -> Path:
    """Write ``which.cmd`` + optional ``ghdl.cmd`` into ``shim_dir``.

    ``ghdl.cmd`` lives in a space-free directory and invokes the real GHDL with
    quotes, so Tcl ``exec $ghdl --version`` works when GHDL is under
    ``Program Files``.
    """
    directory = Path(shim_dir)
    directory.mkdir(parents=True, exist_ok=True)
    # Path.write_text(..., newline=) needs Python 3.10+; keep 3.9-compatible CRLF.
    with (directory / "which.cmd").open("w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(_WHICH_CMD_BODY)

    target = resolve_ghdl_executable_path(ghdl_executable)
    if target:
        bat_path = target.replace("/", "\\")
        with (directory / "ghdl.cmd").open("w", encoding="utf-8", newline="\r\n") as handle:
            handle.write(f'@echo off\r\n"{bat_path}" %*\r\n')
    return directory.resolve()


def build_osvvm_env_bootstrap(
    ghdl_executable: str | None = None,
    *,
    windows_shim_dir: str | None = None,
) -> str:
    """Return TCL that prepares PATH before ``source StartUp.tcl``.

    OSVVM ``VendorScripts_GHDL.tcl`` runs ``exec which ghdl`` then
    ``exec $ghdl --version``. Native Windows has no ``which``, and ``where``
    can return multiple paths (and paths with spaces). When
    ``windows_shim_dir`` is set (see :func:`install_windows_osvvm_shims`), that
    directory is prepended on Windows so OSVVM sees a single space-free
    ``ghdl.cmd``. The Settings GHDL directory is also prepended on all
    platforms as a fallback.
    """
    bin_dir = ghdl_bin_directory(ghdl_executable)
    ghdl_dir_tcl = tcl_quote(bin_dir) if bin_dir else '""'
    shim_tcl = tcl_quote(str(Path(windows_shim_dir).resolve())) if windows_shim_dir else '""'
    return f"""# GHDL Studio: PATH + Windows which/ghdl shims for OSVVM VendorScripts_GHDL.tcl
set _gsGhdlDir {ghdl_dir_tcl}
set _gsShimDir {shim_tcl}
set _gsPrepend ""
if {{$::tcl_platform(platform) eq "windows" && $_gsShimDir ne ""}} {{
  set _gsPrepend $_gsShimDir
  puts "GHDL Studio: using Windows which/ghdl shims in $_gsShimDir"
}}
if {{$_gsGhdlDir ne ""}} {{
  if {{$_gsPrepend ne ""}} {{
    if {{$::tcl_platform(platform) eq "windows"}} {{
      set _gsPrepend "$_gsPrepend;$_gsGhdlDir"
    }} else {{
      set _gsPrepend "$_gsPrepend:$_gsGhdlDir"
    }}
  }} else {{
    set _gsPrepend $_gsGhdlDir
  }}
  puts "GHDL Studio: GHDL directory on PATH: $_gsGhdlDir"
}}
if {{$_gsPrepend ne ""}} {{
  if {{$::tcl_platform(platform) eq "windows"}} {{
    set ::env(PATH) "$_gsPrepend;$::env(PATH)"
  }} else {{
    set ::env(PATH) "$_gsPrepend:$::env(PATH)"
  }}
}}
"""


def build_osvvm_mcode_coverage_guard_tcl() -> str:
    """
    Return TCL that disables OSVVM code coverage for backends that break under gcov.

    Project ``.pro`` files often call ``SetCoverageAnalyzeEnable true`` /
    ``SetCoverageSimulateEnable true``. With GCC/LLVM GHDL that links ``-lgcov``,
    re-running suites then fails with::

        libgcov profiling error:...gcda:overwriting an existing profile data
            with a different checksum

    OSVVM treats those stderr lines as simulate failures even when all
    affirmations passed.

    Behaviour:
    - **mcode** GHDL: always disable coverage (``-fprofile-arcs`` is unsupported).
    - **GCC/LLVM** GHDL: disable coverage by default; set env
      ``GHDL_STUDIO_OSVVM_COVERAGE=1`` to keep project coverage settings.
    """
    return r"""
# GHDL Studio: avoid false SimulateError from libgcov / unsupported coverage flags.
set _ghdl_studio_force_cov 0
if {[info exists ::env(GHDL_STUDIO_OSVVM_COVERAGE)]} {
  set _v [string trim $::env(GHDL_STUDIO_OSVVM_COVERAGE)]
  if {$_v eq "1" || [string tolower $_v] eq "true" || [string tolower $_v] eq "yes"} {
    set _ghdl_studio_force_cov 1
  }
}
set _ghdl_studio_is_mcode 0
if {[catch {exec ghdl --version} _ghdl_studio_ver] == 0} {
  if {[string match -nocase "*mcode*" $_ghdl_studio_ver]} {
    set _ghdl_studio_is_mcode 1
  }
}
# mcode: never enable coverage. GCC/LLVM: off unless GHDL_STUDIO_OSVVM_COVERAGE=1.
if {$_ghdl_studio_is_mcode || !$_ghdl_studio_force_cov} {
  if {[catch {SetCoverageAnalyzeEnable false} _ghdl_studio_cov_err]} {
    puts "GHDL Studio: SetCoverageAnalyzeEnable false: $_ghdl_studio_cov_err"
  } else {
    puts "GHDL Studio: CoverageAnalyzeEnable=false (avoid libgcov / mcode issues)"
  }
  if {[catch {SetCoverageSimulateEnable false} _ghdl_studio_cov_err]} {
    puts "GHDL Studio: SetCoverageSimulateEnable false: $_ghdl_studio_cov_err"
  } else {
    puts "GHDL Studio: CoverageSimulateEnable=false (avoid libgcov / mcode issues)"
  }
}
"""



def osvvm_library_has_randompkg(lib_dir: str | Path) -> bool:
    """Return True if ``lib_dir`` looks like a compiled GHDL ``osvvm`` tree."""
    root = Path(lib_dir).expanduser()
    if not root.is_dir():
        return False
    patterns = (
        "osvvm/**/*.cf",
        "osvvm/**/*RandomPkg*",
        "osvvm/**/*randompkg*",
        "**/osvvm-obj*.cf",
        "osvvm/v08/**",
    )
    for pattern in patterns:
        try:
            if any(root.glob(pattern)):
                return True
        except OSError:
            continue
    return False


def diagnose_osvvm_randompkg(
    pro_file: str,
    *,
    osvvm_lib_path: str = "",
) -> list[str]:
    """Return human-readable warnings when RandomPkg likely cannot load."""
    warnings: list[str] = []
    candidates: list[Path] = []
    configured = (osvvm_lib_path or "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    pro_dir = Path(pro_file).expanduser().resolve().parent
    for root in (pro_dir / "osvvm_ghdl", pro_dir.parent / "osvvm_ghdl"):
        if root.is_dir():
            candidates.append(root)
            candidates.extend(sorted(root.glob("VHDL_LIBS/GHDL-*")))

    seen: set[str] = set()
    found_compiled = False
    checked_any = False
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_dir():
            continue
        checked_any = True
        if osvvm_library_has_randompkg(candidate):
            found_compiled = True
            break

    if checked_any and not found_compiled:
        warnings.append(
            "OSVVM RandomPkg does not look compiled under osvvm_ghdl / OSVVM lib path.\n"
            "Analyze will fail with: cannot load package \"randompkg\".\n"
            "Fix: Simulation → Precompile OSVVM library… with library directory "
            "set to your osvvm_ghdl folder (the parent of VHDL_LIBS)."
        )
    elif not checked_any and not configured:
        warnings.append(
            "No OSVVM lib path / osvvm_ghdl folder found next to the .pro.\n"
            "If testbenches use osvvm.RandomPkg, run Simulation → "
            "Precompile OSVVM library… first (or LinkLibraryDirectory in the .pro)."
        )
    return warnings


def build_osvvm_batch_script(
    startup_tcl: str,
    pro_file: str,
    *,
    ghdl_executable: str | None = None,
    windows_shim_dir: str | None = None,
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
    bootstrap = build_osvvm_env_bootstrap(
        ghdl_executable,
        windows_shim_dir=windows_shim_dir,
    )
    mcode_guard = build_osvvm_mcode_coverage_guard_tcl()
    startup_q = tcl_quote(str(Path(startup_tcl).resolve()))
    pro_q = tcl_quote(str(Path(pro_file).resolve()))
    return f"""# Generated by GHDL Studio — do not edit
{bootstrap}source {startup_q}
{mcode_guard}# Do not fail the process solely because HTML/YAML reports misbehave.
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

    directory = Path(script_dir or tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    # Always materialise Windows shims next to the batch script. On non-Windows
    # hosts they are unused at runtime but keep the batch script self-contained
    # and unit-testable. On Windows, PATH prepend makes OSVVM use them.
    shim_dir = install_windows_osvvm_shims(
        directory / "ghdl_studio_which_shim",
        ghdl_executable,
    )
    content = build_osvvm_batch_script(
        str(startup),
        str(pro_path),
        ghdl_executable=ghdl_executable,
        windows_shim_dir=str(shim_dir),
    )
    script_file = directory / "ghdl_studio_osvvm_run.tcl"
    script_file.write_text(content, encoding="utf-8")

    return OsvvmRunPlan(
        tclsh=tclsh,
        script_path=str(script_file.resolve()),
        cwd=str(pro_path.parent),
        command_display=f"{tclsh} {script_file.resolve()}  # build {pro_path.name}",
    )


def resolve_osvvm_home_directory(scripts_or_startup: str) -> Path | None:
    """Return the OsvvmLibraries root for a Scripts path or ``StartUp.tcl``."""
    raw = (scripts_or_startup or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_file() and path.name == STARTUP_TCL_NAME:
        # …/OsvvmLibraries/Scripts/StartUp.tcl → …/OsvvmLibraries
        return path.resolve().parent.parent
    startup = resolve_startup_tcl(raw)
    if startup is None:
        return None
    return startup.parent.parent


def resolve_osvvm_precompile_target(
    osvvm_home: str | Path,
    target: str = PRECOMPILE_OSVVM,
) -> Path:
    """Resolve the ``.pro`` / directory path passed to OSVVM ``build``.

    ``osvvm`` → ``…/OsvvmLibraries/osvvm`` (utility library, includes RandomPkg).
    ``all`` → ``…/OsvvmLibraries/OsvvmLibraries.pro`` when present, else the home dir.
    """
    home = Path(osvvm_home).expanduser().resolve()
    normalised = (target or PRECOMPILE_OSVVM).strip().lower()
    if normalised not in PRECOMPILE_TARGETS:
        raise ValueError(
            f"Unknown precompile target {target!r}; expected one of {PRECOMPILE_TARGETS}."
        )
    if normalised == PRECOMPILE_OSVVM:
        util = home / "osvvm"
        if not util.is_dir():
            raise FileNotFoundError(
                f"OSVVM utility library not found at '{util}'.\n"
                "Clone OsvvmLibraries with submodules:\n"
                "  git clone --recursive https://github.com/OSVVM/OsvvmLibraries\n"
                "Or:  cd OsvvmLibraries && git submodule update --init osvvm"
            )
        return util
    pro = home / "OsvvmLibraries.pro"
    if pro.is_file():
        return pro
    return home


def find_compiled_ghdl_lib_dir(
    library_directory: Path | str,
    *,
    ghdl_bin: Path | str | None = None,
) -> Path | None:
    """
    Return the best GHDL library folder under library_directory/VHDL_LIBS.

    Prefers a ``GHDL-<version>`` directory that matches the running GHDL binary
    (via :func:`get_ghdl_version`). Falls back to the newest ``GHDL-*`` folder
    by mtime when no version match is available.
    """
    root = Path(library_directory).expanduser().resolve()
    # Caller may already pass …/VHDL_LIBS/GHDL-<ver> (e.g. after Settings apply).
    if root.is_dir() and root.name.startswith("GHDL-"):
        return root
    vhdl_libs = root / "VHDL_LIBS"
    if not vhdl_libs.is_dir():
        # Also accept …/VHDL_LIBS directly.
        if root.is_dir() and root.name == "VHDL_LIBS":
            vhdl_libs = root
        else:
            return None
    if not vhdl_libs.is_dir():
        return None
    candidates = [
        p for p in vhdl_libs.iterdir() if p.is_dir() and p.name.startswith("GHDL-")
    ]
    if not candidates:
        return None

    wanted: str | None = None
    if ghdl_bin is not None:
        try:
            info = get_ghdl_version(str(ghdl_bin))
            # get_ghdl_version returns GhdlVersionInfo, not a bare version string.
            wanted = getattr(info, "version", None) or None
            if wanted is not None:
                wanted = str(wanted).strip() or None
        except Exception:
            wanted = None
    if wanted:
        for cand in candidates:
            suffix = cand.name[len("GHDL-") :]
            if suffix == wanted or suffix.startswith(wanted + ".") or wanted.startswith(suffix):
                return cand.resolve()
        # Also try major.minor prefix match (e.g. wanted 6.0.0 vs dir GHDL-6.0)
        wanted_parts = wanted.split(".")
        for n in range(len(wanted_parts), 0, -1):
            prefix = ".".join(wanted_parts[:n])
            for cand in candidates:
                suffix = cand.name[len("GHDL-") :]
                if suffix == prefix or suffix.startswith(prefix + "."):
                    return cand.resolve()

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0].resolve()



def build_osvvm_precompile_script(
    startup_tcl: str,
    *,
    library_directory: str,
    target: str = PRECOMPILE_OSVVM,
    ghdl_executable: str | None = None,
    windows_shim_dir: str | None = None,
) -> str:
    """Return TCL that ``SetLibraryDirectory`` + ``build`` OSVVM for GHDL."""
    if not startup_tcl:
        raise ValueError("OSVVM StartUp.tcl path is required.")
    lib_dir = (library_directory or "").strip()
    if not lib_dir:
        raise ValueError("A library directory (SetLibraryDirectory) is required.")
    startup_path = Path(startup_tcl).resolve()
    if not startup_path.is_file():
        raise FileNotFoundError(f"StartUp.tcl not found: {startup_tcl}")
    home = resolve_osvvm_home_directory(str(startup_path))
    if home is None:
        raise FileNotFoundError(
            f"Could not resolve OsvvmLibraries home from StartUp.tcl: {startup_tcl}"
        )
    build_target = resolve_osvvm_precompile_target(home, target)

    bootstrap = build_osvvm_env_bootstrap(
        ghdl_executable,
        windows_shim_dir=windows_shim_dir,
    )
    mcode_guard = build_osvvm_mcode_coverage_guard_tcl()
    startup_q = tcl_quote(str(startup_path))
    lib_q = tcl_quote(str(Path(lib_dir).expanduser().resolve()))
    target_q = tcl_quote(str(build_target.resolve()))
    return f"""# Generated by GHDL Studio — precompile OSVVM for GHDL
{bootstrap}source {startup_q}
{mcode_guard}SetLibraryDirectory {lib_q}
puts "GHDL Studio: SetLibraryDirectory={lib_q}"
puts "GHDL Studio: building {target_q}"
if {{[info exists ::osvvm::FailOnReportErrors]}} {{
  set ::osvvm::FailOnReportErrors false
}}
set _ghdlStudioBuildRc [catch {{build {target_q}}} _ghdlStudioBuildMsg]
set _ghdlStudioAnalyzeErr 0
if {{[info exists ::osvvm::AnalyzeErrorCount]}} {{
  set _ghdlStudioAnalyzeErr $::osvvm::AnalyzeErrorCount
}}
if {{[info exists ::osvvm::BuildStatus]}} {{
  puts "GHDL Studio: BuildStatus=$::osvvm::BuildStatus AnalyzeErrors=$_ghdlStudioAnalyzeErr"
}}
if {{$_ghdlStudioAnalyzeErr > 0}} {{
  puts "GHDL Studio: OSVVM precompile failed (analyze errors)."
  if {{$_ghdlStudioBuildRc}} {{
    puts $_ghdlStudioBuildMsg
  }}
  exit 1
}}
if {{$_ghdlStudioBuildRc}} {{
  puts "GHDL Studio: analyze OK; ignoring post-build report error:"
  puts $_ghdlStudioBuildMsg
}}
puts "GHDL Studio: OSVVM precompile finished."
puts "GHDL Studio: set Settings → OSVVM lib path (-P) to the VHDL_LIBS/GHDL-* folder under the library directory."
exit 0
"""


def prepare_osvvm_precompile_run(
    *,
    tclsh: str,
    startup_tcl: str,
    library_directory: str,
    target: str = PRECOMPILE_OSVVM,
    script_dir: str | None = None,
    ghdl_executable: str | None = None,
) -> OsvvmRunPlan:
    """Write a temporary TCL script that precompiles OSVVM into ``library_directory``."""
    if not tclsh:
        raise ValueError("tclsh executable is required.")
    lib_path = Path(library_directory).expanduser()
    lib_path.mkdir(parents=True, exist_ok=True)
    lib_resolved = lib_path.resolve()

    directory = Path(script_dir or tempfile.gettempdir())
    directory.mkdir(parents=True, exist_ok=True)
    shim_dir = install_windows_osvvm_shims(
        directory / "ghdl_studio_which_shim",
        ghdl_executable,
    )
    content = build_osvvm_precompile_script(
        startup_tcl,
        library_directory=str(lib_resolved),
        target=target,
        ghdl_executable=ghdl_executable,
        windows_shim_dir=str(shim_dir),
    )
    script_file = directory / "ghdl_studio_osvvm_precompile.tcl"
    script_file.write_text(content, encoding="utf-8")

    return OsvvmRunPlan(
        tclsh=tclsh,
        script_path=str(script_file.resolve()),
        cwd=str(lib_resolved),
        command_display=(
            f"{tclsh} {script_file.resolve()}  # precompile OSVVM ({target}) → {lib_resolved}"
        ),
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
