"""Tests for ``.ghdlstudio`` project save/load."""

from pathlib import Path

import pytest

from ghdl_studio.osvvm_commands import MODE_NORMAL, MODE_OSVVM
from ghdl_studio.project_file import (
    PROJECT_FORMAT,
    StudioProject,
    load_project_file,
    project_from_dict,
    project_to_dict,
    save_project_file,
)


def test_roundtrip_relative_paths(tmp_path):
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    src = rtl / "foo.vhd"
    src.write_text("entity foo is end;")
    pro = tmp_path / "run.pro"
    pro.write_text("library osvvm\n")

    project = StudioProject(
        mode=MODE_OSVVM,
        files=[str(src)],
        pro_files=[str(pro)],
        active_pro=str(pro),
        top_unit="foo_tb",
        stop_time="200ns",
        std="08",
        output_dir="output",
        generics={"WIDTH": "8"},
    )
    out = save_project_file(tmp_path / "demo.ghdlstudio", project)
    assert out.name == "demo.ghdlstudio"
    raw = out.read_text(encoding="utf-8")
    assert PROJECT_FORMAT in raw
    assert '"rtl/foo.vhd"' in raw or '"rtl\\\\foo.vhd"' in raw.replace("\\\\", "/")
    assert "run.pro" in raw

    loaded = load_project_file(out)
    assert loaded.mode == MODE_OSVVM
    assert loaded.top_unit == "foo_tb"
    assert loaded.stop_time == "200ns"
    assert loaded.generics == {"WIDTH": "8"}
    assert Path(loaded.files[0]).resolve() == src.resolve()
    assert Path(loaded.active_pro).resolve() == pro.resolve()


def test_reject_unknown_format():
    with pytest.raises(ValueError, match="Unsupported project format"):
        project_from_dict({"format": "other", "version": 1}, base_dir=".")


def test_reject_future_version():
    with pytest.raises(ValueError, match="newer"):
        project_from_dict(
            {"format": PROJECT_FORMAT, "version": 99, "mode": MODE_NORMAL},
            base_dir=".",
        )


def test_project_to_dict_defaults():
    data = project_to_dict(StudioProject(mode=MODE_NORMAL), base_dir=".")
    assert data["format"] == PROJECT_FORMAT
    assert data["mode"] == MODE_NORMAL
    assert data["run"]["std"] == "08"
