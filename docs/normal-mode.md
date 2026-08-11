# Normal mode

Use Normal mode when you manage VHDL (and optional Verilog / data) files yourself
and drive GHDL with **Analyze → Elaborate → Run**.

![Normal mode with editor and project files](images/docs_normal_mode.png){ width="900" }

## Project files

In the **Project files** dock:

1. **Add file…** — VHDL (`.vhd`/`.vhdl`), Verilog/SystemVerilog (`.v`/`.sv`), or data/stimulus files
2. **Move up / Move down** — compile order for `ghdl -a` (VHDL only)
3. Double-click a file to open it in the **Editor** tab

Verilog and data files are colour-marked and skipped during Analyze; data files
still help locate the project root so paths like `../input/…` work.

## Toolbar

| Control | Purpose |
|---------|---------|
| **Top-level entity** | Entity for Elaborate / Run (auto-filled from scanned VHDL) |
| **Stop time** | Optional `--stop-time=` for Run (e.g. `200ns`) |
| **Generics…** | Optional `-gNAME=value` overrides for Run (saved in `.ghdlstudio`) |
| **Analyze / Elaborate / Run** | Individual GHDL steps (do not auto-chain) |
| **Analyze + Elaborate + Run** | Full chain |
| **Precompile OSVVM library…** | Build `osvvm` for Normal-mode `-P` |
| **Clean** | `ghdl --clean` + clear Studio `output/` in Normal mode |

## Editor

- Line numbers
- Syntax highlighting for **VHDL** and **Verilog / SystemVerilog**
- Save with **Ctrl+S** / **File → Save**
- Closing the app, a tab, or opening another project prompts **Save / Discard / Cancel** when editors or the `.ghdlstudio` project are dirty

## Output & waveforms

The **Output** dock shows colour-coded GHDL (and OSVVM transcript) lines, plus a
short **session history** of Analyze / Elaborate / Run / Build (timestamp + exit code).

The **Problems** dock lists GHDL `file:line:col:error|warning` diagnostics
(classic and split formats); double-click opens the editor at that location.
The list clears when a new Analyze / Elaborate / Build starts.

After a successful Normal-mode **Run**, if GCC coverage files (`.gcda` / `.gcno`)
are present under `output/`, a short hint is logged (silent when none exist).

After a successful Run, GHDL Studio opens the waveform in the **Waveforms** tab:

- **Surfer** embedded when found and enabled in Settings
- otherwise the built-in VCD viewer

## Output directory

Default work directory is `output/` (configurable). Relative testbench paths
such as `../input/ref_wave_data.txt` resolve next to that folder. Studio also
stages project data files into `<output>/../input/` before Run when needed.
