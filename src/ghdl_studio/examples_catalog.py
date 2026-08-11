"""Locate shipped example projects (counter, adder)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM


@dataclass(frozen=True)
class ExampleSpec:
    """Files and defaults for a one-click example load."""

    name: str
    mode: str
    files: tuple[str, ...]
    pro_files: tuple[str, ...] = ()
    active_pro: str = ""
    top_unit: str = ""
    stop_time: str = ""


def find_examples_root() -> Path | None:
    """Return the ``examples/`` directory if counter/adder sources are present."""
    env = (os.environ.get("GHDL_STUDIO_EXAMPLES") or "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    # PyInstaller portable: examples/ next to GHDL-Studio.exe (or under _MEIPASS).
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "examples")
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "examples")
    here = Path(__file__).resolve()
    # Editable / repo checkout: src/ghdl_studio/examples_catalog.py → repo/examples
    candidates.append(here.parents[2] / "examples")
    # Optional next to the package: ghdl_studio/examples
    candidates.append(here.parent / "examples")
    candidates.append(Path.cwd() / "examples")
    for candidate in candidates:
        root = candidate.expanduser()
        if (root / "counter" / "counter.vhd").is_file():
            try:
                return root.resolve()
            except OSError:
                return root
    return None


def counter_example(root: Path | None = None) -> ExampleSpec | None:
    base = root or find_examples_root()
    if base is None:
        return None
    files = (
        str((base / "counter" / "counter.vhd").resolve()),
        str((base / "counter" / "counter_tb.vhd").resolve()),
    )
    if not all(Path(p).is_file() for p in files):
        return None
    return ExampleSpec(
        name="Counter (Normal)",
        mode=MODE_NORMAL,
        files=files,
        top_unit="counter_tb",
        stop_time="200ns",
    )


def adder_normal_example(root: Path | None = None) -> ExampleSpec | None:
    base = root or find_examples_root()
    if base is None:
        return None
    files = (
        str((base / "adder" / "adder.vhd").resolve()),
        str((base / "adder" / "adder_tb.vhd").resolve()),
    )
    if not all(Path(p).is_file() for p in files):
        return None
    return ExampleSpec(
        name="Adder (Normal + OSVVM TB)",
        mode=MODE_NORMAL,
        files=files,
        top_unit="adder_tb",
    )


def adder_osvvm_example(root: Path | None = None) -> ExampleSpec | None:
    base = root or find_examples_root()
    if base is None:
        return None
    pro = base / "adder" / "adder.pro"
    if not pro.is_file():
        return None
    resolved = str(pro.resolve())
    return ExampleSpec(
        name="Adder (OSVVM .pro)",
        mode=MODE_OSVVM,
        files=(),
        pro_files=(resolved,),
        active_pro=resolved,
        top_unit="adder_tb",
    )
