"""Native vs WSL tool backend helpers (Qt-free).

On native Windows the GUI can optionally launch GHDL / tclsh / Surfer through
``wsl.exe`` so Linux toolchains under WSL are used with ``/mnt/c/...`` paths.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

TOOL_BACKEND_NATIVE = "native"
TOOL_BACKEND_WSL = "wsl"
TOOL_BACKENDS = (TOOL_BACKEND_NATIVE, TOOL_BACKEND_WSL)
DEFAULT_TOOL_BACKEND = TOOL_BACKEND_NATIVE

_DRIVE_PATH_RE = re.compile(r"^([A-Za-z]):([\\/].*)$")
_UNC_RE = re.compile(r"^\\\\[^\\]+\\[^\\]+")


def is_windows() -> bool:
    return sys.platform.startswith("win")


def normalize_tool_backend(value: str | None) -> str:
    key = (value or "").strip().lower()
    if key in TOOL_BACKENDS:
        return key
    return DEFAULT_TOOL_BACKEND


def windows_path_to_wsl(path: str) -> str:
    """Translate a Windows path to a WSL ``/mnt/<drive>/…`` path.

    Already-Unix paths (including ``/mnt/…``) are returned unchanged (with
    backslashes normalised to forward slashes). Relative paths are unchanged.
    """
    raw = (path or "").strip()
    if not raw:
        return raw
    normalised = raw.replace("\\", "/")
    if normalised.startswith("/"):
        return normalised
    if len(normalised) >= 2 and normalised[1] == ":":
        drive = normalised[0].lower()
        rest = normalised[2:]
        if not rest.startswith("/"):
            rest = "/" + rest
        return f"/mnt/{drive}{rest}"
    return normalised


def wsl_path_to_windows(path: str) -> str:
    """Best-effort reverse of :func:`windows_path_to_wsl`` (``/mnt/c/…`` → ``C:\\…``)."""
    raw = (path or "").strip().replace("\\", "/")
    if raw.startswith("/mnt/") and len(raw) >= 7 and raw[6] == "/":
        drive = raw[5].upper()
        rest = raw[6:].replace("/", "\\")
        return f"{drive}:{rest}"
    return path


def find_wsl_executable() -> str | None:
    """Return ``wsl.exe`` / ``wsl`` on PATH when available."""
    for name in ("wsl.exe", "wsl"):
        found = shutil.which(name)
        if found:
            return found
    return None


def probe_wsl(*, timeout: float = 8.0) -> tuple[bool, str]:
    """Return ``(ok, message)`` after probing ``wsl.exe -e true``."""
    wsl = find_wsl_executable()
    if not wsl:
        return (
            False,
            "WSL is not available (wsl.exe not found on PATH). "
            "Install Windows Subsystem for Linux or switch Tool backend to Native.",
        )
    try:
        completed = subprocess.run(
            [wsl, "-e", "true"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"WSL probe failed: {exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        suffix = f" ({detail})" if detail else ""
        return (
            False,
            "WSL is installed but not usable"
            f"{suffix}. Open a WSL terminal once, or switch Tool backend to Native.",
        )
    return True, "WSL is available."


def looks_like_filesystem_path(token: str) -> bool:
    """Heuristic: absolute Windows/Unix path or ``--flag=/abs/path`` value."""
    if not token:
        return False
    if "=" in token and not token.startswith("="):
        # Keep flag name; only the value may be a path.
        _flag, _, value = token.partition("=")
        return looks_like_filesystem_path(value)
    if token.startswith("/") or _DRIVE_PATH_RE.match(token.replace("/", "\\")):
        return True
    if len(token) >= 3 and token[1] == ":" and token[2] in "/\\":
        return True
    return False


def translate_path_token(token: str, *, to_wsl: bool) -> str:
    """Translate a CLI token that may embed an absolute path after ``=``."""
    if not to_wsl:
        return token
    if "=" in token and not token.startswith("="):
        flag, sep, value = token.partition("=")
        if looks_like_filesystem_path(value):
            return f"{flag}{sep}{windows_path_to_wsl(value)}"
        return token
    if looks_like_filesystem_path(token):
        return windows_path_to_wsl(token)
    return token


@dataclass(frozen=True)
class ProcessInvocation:
    """Concrete process to start via :class:`GhdlRunner` / ``QProcess``."""

    executable: str
    args: list[str]
    cwd: str | None
    display: str


def wrap_for_backend(
    executable: str,
    args: list[str] | None = None,
    cwd: str | None = None,
    *,
    backend: str | None = None,
    translate_paths: bool = True,
) -> ProcessInvocation:
    """Return a process invocation for *backend* (native identity or ``wsl.exe``).

    When *backend* is WSL:
    - Outer executable becomes ``wsl.exe``
    - Working directory is passed via ``--cd <wsl_cwd>``
    - Absolute Windows paths in *args* / *cwd* / *executable* are translated
    """
    argv = list(args or [])
    fmt = normalize_tool_backend(backend)
    if fmt != TOOL_BACKEND_WSL:
        display = " ".join([executable, *argv])
        return ProcessInvocation(executable=executable, args=argv, cwd=cwd, display=display)

    wsl = find_wsl_executable()
    if not wsl:
        raise RuntimeError(
            "WSL is not available (wsl.exe not found on PATH). "
            "Install WSL or switch Tool backend to Native."
        )

    tool = executable.strip()
    # Windows Settings often store ``C:\\…\\ghdl.exe``. Prefer the Linux PATH
    # name inside WSL for Windows PE toolchains (``.exe``). Elaborated
    # simulation binaries are extensionless ELF files under ``/mnt/c/…`` and
    # must keep a full translated path — a bare name is not on PATH even with
    # ``wsl --cd``.
    normalised_tool = tool.replace("\\", "/")
    if looks_like_filesystem_path(tool):
        if normalised_tool.lower().endswith(".exe"):
            base = normalised_tool.rsplit("/", 1)[-1][:-4]
            tool = base or tool
        elif translate_paths:
            tool = windows_path_to_wsl(tool)

    translated_args = [
        translate_path_token(arg, to_wsl=translate_paths) for arg in argv
    ]
    wsl_args: list[str] = []
    wsl_cwd = None
    if cwd:
        wsl_cwd = windows_path_to_wsl(cwd) if translate_paths else cwd
        wsl_args.extend(["--cd", wsl_cwd])
    wsl_args.extend(["-e", tool, *translated_args])
    display = " ".join([wsl, *wsl_args])
    # QProcess working directory stays on the Windows side (optional).
    return ProcessInvocation(executable=wsl, args=wsl_args, cwd=None, display=display)


def wsl_which(tool: str, *, timeout: float = 8.0) -> str | None:
    """Resolve *tool* inside the default WSL distro (``wsl -e which <tool>``)."""
    wsl = find_wsl_executable()
    if not wsl:
        return None
    try:
        completed = subprocess.run(
            [wsl, "-e", "which", tool],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    line = (completed.stdout or "").strip().splitlines()
    return line[0] if line else None
