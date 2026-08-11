"""Tests for Native / WSL tool backend helpers."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from ghdl_studio.tool_backend import (
    TOOL_BACKEND_NATIVE,
    TOOL_BACKEND_WSL,
    normalize_tool_backend,
    translate_path_token,
    windows_path_to_wsl,
    wsl_path_to_windows,
    wrap_for_backend,
)


def test_normalize_tool_backend():
    assert normalize_tool_backend("WSL") == TOOL_BACKEND_WSL
    assert normalize_tool_backend("native") == TOOL_BACKEND_NATIVE
    assert normalize_tool_backend("nope") == TOOL_BACKEND_NATIVE


def test_windows_path_to_wsl_drive_and_posix():
    assert windows_path_to_wsl(r"C:\Users\me\a.vhd") == "/mnt/c/Users/me/a.vhd"
    assert windows_path_to_wsl("D:/proj/out") == "/mnt/d/proj/out"
    assert windows_path_to_wsl("/mnt/c/already") == "/mnt/c/already"
    assert windows_path_to_wsl("relative/path") == "relative/path"


def test_wsl_path_to_windows():
    assert wsl_path_to_windows("/mnt/c/Users/me/a.vhd").replace("/", "\\") == (
        r"C:\Users\me\a.vhd"
    )


def test_translate_path_token_flag_and_plain():
    assert (
        translate_path_token(r"--workdir=C:\out", to_wsl=True)
        == "--workdir=/mnt/c/out"
    )
    assert translate_path_token(r"C:\a.vhd", to_wsl=True) == "/mnt/c/a.vhd"
    assert translate_path_token("--std=08", to_wsl=True) == "--std=08"


def test_wrap_for_backend_native_identity():
    inv = wrap_for_backend("ghdl", ["-a", "a.vhd"], cwd="/tmp", backend="native")
    assert inv.executable == "ghdl"
    assert inv.args == ["-a", "a.vhd"]
    assert inv.cwd == "/tmp"


def test_wrap_for_backend_wsl_translates(monkeypatch):
    monkeypatch.setattr(
        "ghdl_studio.tool_backend.find_wsl_executable",
        lambda: r"C:\Windows\System32\wsl.exe",
    )
    inv = wrap_for_backend(
        r"C:\tools\ghdl.exe",
        [r"--workdir=C:\proj\output", r"C:\proj\tb.vhd"],
        cwd=r"C:\proj\output",
        backend=TOOL_BACKEND_WSL,
    )
    assert inv.executable.endswith("wsl.exe")
    assert inv.cwd is None
    assert "--cd" in inv.args
    assert "/mnt/c/proj/output" in inv.args
    assert "-e" in inv.args
    assert "ghdl" in inv.args  # stripped Windows .exe path → bare name
    assert "--workdir=/mnt/c/proj/output" in inv.args
    assert "/mnt/c/proj/tb.vhd" in inv.args


def test_wrap_for_backend_wsl_missing_raises(monkeypatch):
    monkeypatch.setattr("ghdl_studio.tool_backend.find_wsl_executable", lambda: None)
    with pytest.raises(RuntimeError, match="WSL is not available"):
        wrap_for_backend("ghdl", [], backend=TOOL_BACKEND_WSL)
