"""GHDL Studio project file (``.ghdlstudio``) — Qt-free, unit-testable."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ghdl_studio.ghdl_commands import (
    DEFAULT_ANALYZE_EXTRA_ARGS,
    DEFAULT_ELABORATE_EXTRA_ARGS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RUN_EXTRA_ARGS,
    DEFAULT_STD,
    DEFAULT_WAVE_FORMAT,
    normalize_wave_format,
)
from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM

PROJECT_FORMAT = "ghdl-studio-project"
PROJECT_VERSION = 1
PROJECT_EXTENSION = ".ghdlstudio"
PROJECT_FILE_FILTER = "GHDL Studio project (*.ghdlstudio);;JSON (*.json);;All files (*)"


@dataclass
class StudioProject:
    """Serializable Studio session (sources, mode, run options)."""

    mode: str = MODE_NORMAL
    files: list[str] = field(default_factory=list)
    pro_files: list[str] = field(default_factory=list)
    active_pro: str = ""
    top_unit: str = ""
    stop_time: str = ""
    std: str = DEFAULT_STD
    output_dir: str = DEFAULT_OUTPUT_DIR
    osvvm_lib_path: str = ""
    custom_lib_path: str = ""
    generics: dict[str, str] = field(default_factory=dict)
    wave_format: str = DEFAULT_WAVE_FORMAT
    extra_analyze_args: list[str] = field(
        default_factory=lambda: list(DEFAULT_ANALYZE_EXTRA_ARGS)
    )
    extra_elaborate_args: list[str] = field(
        default_factory=lambda: list(DEFAULT_ELABORATE_EXTRA_ARGS)
    )
    extra_run_args: list[str] = field(
        default_factory=lambda: list(DEFAULT_RUN_EXTRA_ARGS)
    )

    def normalized_mode(self) -> str:
        return MODE_OSVVM if self.mode == MODE_OSVVM else MODE_NORMAL


def _to_relative(path: str, base: Path) -> str:
    if not path:
        return ""
    absolute = Path(path).expanduser()
    try:
        absolute = absolute.resolve()
    except OSError:
        absolute = Path(path).expanduser()
    try:
        return absolute.relative_to(base).as_posix()
    except ValueError:
        return absolute.as_posix()


def _to_absolute(path: str, base: Path) -> str:
    if not path:
        return ""
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        return str(candidate.resolve())
    except OSError:
        return str(candidate)


def project_to_dict(project: StudioProject, *, base_dir: str | Path) -> dict:
    """Serialize *project* with paths relative to *base_dir* when possible."""
    base = Path(base_dir).expanduser().resolve()
    mode = project.normalized_mode()
    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_VERSION,
        "mode": mode,
        "files": [_to_relative(p, base) for p in project.files if p],
        "pro_files": [_to_relative(p, base) for p in project.pro_files if p],
        "active_pro": _to_relative(project.active_pro, base),
        "run": {
            "top_unit": project.top_unit or "",
            "stop_time": project.stop_time or "",
            "std": project.std or DEFAULT_STD,
            "output_dir": project.output_dir or DEFAULT_OUTPUT_DIR,
            "osvvm_lib_path": _to_relative(project.osvvm_lib_path, base)
            if project.osvvm_lib_path
            else "",
            "custom_lib_path": _to_relative(project.custom_lib_path, base)
            if project.custom_lib_path
            else "",
            "generics": dict(project.generics or {}),
            "wave_format": normalize_wave_format(project.wave_format),
            "extra_analyze_args": list(project.extra_analyze_args or []),
            "extra_elaborate_args": list(project.extra_elaborate_args or []),
            "extra_run_args": list(project.extra_run_args or []),
        },
    }


def project_from_dict(data: dict, *, base_dir: str | Path) -> StudioProject:
    """Deserialize a project dict, resolving relative paths against *base_dir*."""
    if not isinstance(data, dict):
        raise ValueError("Project file must contain a JSON object.")
    fmt = data.get("format")
    if fmt not in (None, PROJECT_FORMAT):
        raise ValueError(f"Unsupported project format: {fmt!r}")
    version = data.get("version", 1)
    try:
        version_i = int(version)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid project version: {version!r}") from exc
    if version_i > PROJECT_VERSION:
        raise ValueError(
            f"Project file version {version_i} is newer than this GHDL Studio "
            f"({PROJECT_VERSION}). Please upgrade GHDL Studio."
        )

    base = Path(base_dir).expanduser().resolve()
    run = data.get("run") or {}
    if not isinstance(run, dict):
        raise ValueError("'run' must be an object when present.")

    mode = str(data.get("mode") or MODE_NORMAL).strip().lower()
    if mode not in (MODE_NORMAL, MODE_OSVVM):
        mode = MODE_NORMAL

    files = [
        _to_absolute(str(p), base)
        for p in (data.get("files") or [])
        if str(p or "").strip()
    ]
    pro_files = [
        _to_absolute(str(p), base)
        for p in (data.get("pro_files") or [])
        if str(p or "").strip()
    ]
    active_pro = _to_absolute(str(data.get("active_pro") or ""), base)
    if active_pro and active_pro not in pro_files:
        pro_files.insert(0, active_pro)

    osvvm_lib = str(run.get("osvvm_lib_path") or "").strip()
    custom_lib = str(run.get("custom_lib_path") or "").strip()
    generics_raw = run.get("generics") or {}
    generics: dict[str, str] = {}
    if isinstance(generics_raw, dict):
        for key, value in generics_raw.items():
            generics[str(key)] = str(value)

    return StudioProject(
        mode=mode,
        files=files,
        pro_files=pro_files,
        active_pro=active_pro,
        top_unit=str(run.get("top_unit") or ""),
        stop_time=str(run.get("stop_time") or ""),
        std=str(run.get("std") or DEFAULT_STD),
        output_dir=str(run.get("output_dir") or DEFAULT_OUTPUT_DIR),
        osvvm_lib_path=_to_absolute(osvvm_lib, base) if osvvm_lib else "",
        custom_lib_path=_to_absolute(custom_lib, base) if custom_lib else "",
        generics=generics,
        wave_format=normalize_wave_format(str(run.get("wave_format") or DEFAULT_WAVE_FORMAT)),
        extra_analyze_args=[str(a) for a in (run.get("extra_analyze_args") or [])],
        extra_elaborate_args=[str(a) for a in (run.get("extra_elaborate_args") or [])],
        extra_run_args=[str(a) for a in (run.get("extra_run_args") or [])],
    )


def save_project_file(path: str | Path, project: StudioProject) -> Path:
    """Write *project* as JSON to *path* and return the resolved path."""
    target = Path(path).expanduser()
    if target.suffix.lower() not in {".ghdlstudio", ".json"}:
        target = target.with_suffix(PROJECT_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    base = target.parent.resolve()
    payload = project_to_dict(project, base_dir=base)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    target.write_text(text, encoding="utf-8")
    return target.resolve()


def load_project_file(path: str | Path) -> StudioProject:
    """Load a :class:`StudioProject` from *path*."""
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Project file not found: {target}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in project file: {exc}") from exc
    return project_from_dict(data, base_dir=target.parent)
