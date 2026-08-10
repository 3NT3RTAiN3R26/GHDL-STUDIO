# GHDL Studio

**Version 0.6.0** — a cross-platform graphical interface for
[GHDL](https://ghdl.github.io/ghdl/), built with Python and PySide6.

Runs on **Linux**, **Windows**, and **WSL** with the same dark Fusion theme.

![Normal mode workspace](images/docs_normal_mode.png){ width="900" }

## What you can do

| Area | Highlights |
|------|------------|
| **Modes** | **Normal GHDL** (manual files) or **OSVVM** (`.pro` via TCL) |
| **Project files** | VHDL, Verilog/SystemVerilog, data files — or multiple `.pro` scripts |
| **Editor** | Line numbers + VHDL / Verilog syntax highlighting |
| **Simulation** | Analyze / Elaborate / Run, or **Build .pro (OSVVM)** |
| **Waveforms** | Embedded [Surfer](https://surfer-project.org/) or built-in VCD viewer |
| **OSVVM** | Precompile library, HTML report tab, colour-coded transcript |

## Choose a workflow

![Startup mode dialog](images/docs_startup_mode.png){ width="480" }

- **Normal GHDL** — add sources, pick a top-level entity, set stop time, run the classic `-a` / `-e` / `-r` flow.
- **OSVVM** — select one or more `.pro` scripts, mark the active one, then **Build .pro**.

## Quick links

- [Getting started](getting-started.md) — install & launch
- [Normal mode](normal-mode.md) — project files, editor, Analyze → Run
- [OSVVM mode](osvvm-mode.md) — multiple `.pro` files, Build, reports
- [Settings](settings.md) — GHDL, Surfer, TCL, OSVVM paths
- [Examples](examples.md) — counter & adder

## Source & licence

- Repository: [github.com/3NT3RTAiN3R26/GHDL-STUDIO](https://github.com/3NT3RTAiN3R26/GHDL-STUDIO)
- Licence: see [LICENSE](https://github.com/3NT3RTAiN3R26/GHDL-STUDIO/blob/main/LICENSE) in the repo
