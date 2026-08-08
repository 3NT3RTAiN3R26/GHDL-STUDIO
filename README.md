# GHDL Studio

A cross-platform graphical interface for [GHDL](https://ghdl.github.io/ghdl/),
the open-source VHDL simulator. Built with **Python** and **PySide6** (Qt for Python),
GHDL Studio runs unchanged on Linux, Windows and macOS.

On **every operating system** the interface uses a consistent dark theme
(Fusion style + dark palette), independent of the system appearance.

## Features (current status)

- Manage source files in a project (add/remove), both **VHDL**
  (`.vhd`/`.vhdl`) and **Verilog/SystemVerilog** (`.v`/`.sv`) — Verilog files are
  colour-highlighted and skipped during the `Analyze` step with a note in the
  log console, because GHDL can only analyse/simulate VHDL
- Simple code editor with VHDL syntax highlighting for viewing/editing files
- **Choose the top-level entity with a click**: a toolbar on the main window shows a
  combo box of all VHDL entities found in the project files (updated automatically
  when files change); you can also type the name freely
- **Set the simulation stop time on the main window** (stop-time field in the same
  toolbar, e.g. `200ns`), without opening the settings dialog
- Asynchronous execution of GHDL commands via `QProcess` (does not block the GUI):
  - **Analyze** (`ghdl -a`)
  - **Elaborate** (`ghdl -e`)
  - **Run** (`ghdl -r`), including VCD and GHW export (`--vcd=` / `--wave=`), stop time and generics
  - Combined flow "Analyze + Elaborate + Run"
- **Dedicated output directory** (default `output/`, configurable in Settings):
  Analyze/Elaborate/Run run with this directory as the working directory, so the work
  library (`work-obj*.cf`), object files (`*.o`), waveform dumps (`*.vcd`/`*.ghw`), coverage data
  (`*.gcda`/`*.gcno`) and the elaborated simulation executable land there instead of
  cluttering the project root. Via Simulation → **"Clean"** (also a
  toolbar button) you can clear the output directory at any time —
  similar to a `clean` target in a GHDL Makefile
- Live log console with colour coding (command / output / error / success)
- **Fully embedded [Surfer](https://surfer-project.org/)** in the "Waveforms" tab:
  If Surfer is installed, it is started automatically after each simulation run and its
  window is embedded natively in the GUI. Embedding works on **Linux/X11**
  (via `python-xlib` + `XReparentWindow`, including a full window-tree search; start prefers
  the Qt `xcb` plugin) and **Windows** (via WinAPI `SetParent`). On other platforms, or
  if Surfer is not found/disabled, a built-in
  **waveform viewer** is used as a fallback: a custom VCD parser with digital signals, bus values
  (as hex), a time ruler, and Zoom In / Zoom Fit / Zoom Out
- Settings dialog for the GHDL path and Surfer path (automatic detection via `PATH`
  or manual selection; Surfer integration can be enabled/disabled), the VHDL standard (87/93/00/02/08),
  and optional **OSVVM lib path** / **Custom lib path** directories (passed to Analyze/Elaborate/Run as `-P`)
- Configurable extra flags for GHDL builds with the GCC backend, pre-filled by default
  and adjustable in the settings dialog or reset with "Default":
  - `ghdl -a`: `-Wc,-fprofile-arcs -Wc,-ftest-coverage -fsynopsys -fPIE`
  - `ghdl -e`: `-Wl,-lgcov -fsynopsys -fPIE`
  - `ghdl -r`: `-fsynopsys`
- Settings are persisted across platforms via `QSettings`

## Project layout

```
src/ghdl_studio/
├── app.py                 # Entry point (QApplication + MainWindow)
├── main_window.py          # Main window, wires all widgets together
├── ghdl_commands.py         # Pure helpers to build GHDL CLI arguments (Qt-free, testable)
├── ghdl_runner.py            # Asynchronous process execution via QProcess
├── vcd_parser.py             # Minimal VCD parser + time formatting (Qt-free, testable)
├── vhdl_scanner.py            # Detection of VHDL entities / Verilog modules (Qt-free, testable)
├── surfer_embed.py             # Native embedding of the Surfer window (Linux/X11, Windows)
├── theme.py                   # Dark Fusion theme (cross-platform)
├── settings.py                # Persistent settings (QSettings)
└── widgets/
    ├── file_explorer.py       # Project file management
    ├── log_console.py          # Colour-coded output console
    ├── code_editor.py           # Text editor for VHDL files
    ├── vhdl_highlighter.py       # VHDL syntax highlighting
    ├── waveform_viewer.py         # Fallback waveform view from VCD data, including time ruler
    └── run_settings_dialog.py     # Settings dialog (GHDL/Surfer path, standard, flags)

examples/counter/            # Example: simple counter + testbench
tests/                        # Unit tests for the Qt-independent modules
```

## Requirements

- Python 3.9 or newer
- **Linux/WSL (Qt-xcb for Surfer embedding):** additionally
  ```bash
  sudo apt install libxcb-cursor0
  ```
  Without this package, Qt 6.5+ will not start with the xcb plugin
  (`xcb-cursor0 or libxcb-cursor0 is needed`). GHDL Studio then tries
  to start without forcing xcb (GUI runs; Surfer embedding may not).
- [GHDL](https://ghdl.github.io/ghdl/getting.html) must be installed and on the `PATH`
  (or set the path manually in the GUI settings).
  - Linux: via the package manager (e.g. `apt install ghdl`) or from GitHub releases
  - Windows: ready-made binary packages from the [GHDL releases page](https://github.com/ghdl/ghdl/releases)
  - macOS: via [Homebrew](https://formulae.brew.sh/formula/ghdl) (`brew install ghdl`)
- **Optional, but recommended:** [Surfer](https://surfer-project.org/) for the full
  embedded waveform display (see above). Without Surfer the GUI still works
  fully via the built-in fallback viewer.
  - **Recommended (no Rust/Cargo):** download pre-built binaries.
    On **Ubuntu 22.04 / WSL** please use the **Rocky Linux binary** — the normal
    `surfer_linux_*.zip` often needs GLIBC ≥ 2.38/2.39 and will not start there.
    ```bash
    mkdir -p ~/.local/bin
    curl -L -o /tmp/surfer_linux_rocky.zip \
      "https://gitlab.com/api/v4/projects/42073614/jobs/artifacts/main/raw/surfer_linux_rocky.zip?job=rocky_build"
    unzip -o /tmp/surfer_linux_rocky.zip -d /tmp/surfer_extract
    install -m 755 /tmp/surfer_extract/surfer ~/.local/bin/surfer
    # Persist PATH if needed:
    grep -q '\$HOME/.local/bin' ~/.bashrc || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    surfer --version
    ```
    Newer distros (e.g. Ubuntu 24.04) can instead use the release zips from
    [Surfer releases](https://gitlab.com/surfer-project/surfer/-/releases)
    (`surfer_linux_v*.zip`).
    Windows: extract `surfer_win_*.zip` from the same page and add the folder containing
    `surfer.exe` to `PATH`, or enter the full path in the GHDL Studio settings.
  - **Alternative from source** (requires Rust): first install
    [rustup](https://rustup.rs/), then
    `cargo install --git https://gitlab.com/surfer-project/surfer.git surfer`
  - On Linux the Python package `python-xlib` is also required to embed Surfer
    (installed automatically with `pip install -r requirements.txt`)
  - Further details: [Surfer documentation](https://docs.surfer-project.org/book/)

### Troubleshooting: Surfer embedding

Surfer may open as a **standalone** window (the simulation is not
affected) but is not embedded in the "Waveforms" tab. Possible causes:

1. **Surfer not on PATH.** Use "Detect automatically" in Settings, or set the
   path to the `surfer` executable manually.
2. **`python-xlib` missing** (Linux only). In the activated venv run
   `pip install -r requirements.txt` again.
3. **Slow window manager/compositor** (e.g. under WSLg): click
   "Retry Surfer".
4. **Surfer embedding reports `currently: wayland`:** Embedding needs Qt-xcb.
   Often `export QT_QPA_PLATFORM=wayland` is still set in the shell (an earlier workaround).
   ```bash
   sudo apt install libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 \
     libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-shape0 \
     libxcb-randr0 libxkbcommon-x11-0 libxcb-util1
   unset QT_QPA_PLATFORM
   # xcb test (must run without aborting):
   QT_QPA_PLATFORM=xcb python3 -c "from PySide6.QtWidgets import QApplication; print(QApplication([]).platformName())"
   git pull origin cursor/ghdl-gui-pyside6-scaffold-85f1
   pip install -e .
   ghdl-studio
   ```
   The app prefers xcb automatically once the probe succeeds — even if
   `QT_QPA_PLATFORM=wayland` was set before. Force Wayland only if needed with
   `export GHDL_STUDIO_PREFER_WAYLAND=1`.
5. **`platform plugin does not support foreign windows` (WSL/Wayland):** At start, GHDL Studio
   automatically sets `QT_QPA_PLATFORM=xcb` if `libxcb-cursor` is found.
   Fully restart the app. If `QT_QPA_PLATFORM=wayland` is set manually:
   temporarily `export QT_QPA_PLATFORM=xcb` (after installing `libxcb-cursor0`).
6. **Windows: empty tab, Surfer stays external:** Embedding uses `SetParent` with
   correct 32-bit `LONG` normalisation — pull the current branch and retest.
7. **Linux/WSL: status "Surfer (embedded)", but empty tab:** Surfer is a GPU app
   (wgpu); after `XReparentWindow` the content often stays black under WSLg/XWayland.
   The current code prefers `QWindow.createWindowContainer` under xcb. Please
   pull the branch and retest. If the tab stays empty, use Surfer as a separate window
   (the internal viewer still shows the waves) — under native Windows,
   embedding is more reliable.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

The last step (`pip install -e .`) installs the `ghdl_studio` package itself
(editable, i.e. source changes take effect immediately) and is **required**
for `python -m ghdl_studio` or the `ghdl-studio` command to work. Without it
startup fails with `No module named ghdl_studio`, because `requirements.txt`
only installs the PySide6 dependency, not the project itself.

## Launch

```bash
python -m ghdl_studio
```

or, thanks to the editable install:

```bash
ghdl-studio
```

## Try the example project

1. Start the GUI
2. Via "Project files" → "Add file..." add the files from `examples/counter/`
   (`counter.vhd`, `counter_tb.vhd`)
3. In the toolbar click the "Top-level entity" drop-down arrow and
   select `counter_tb` (detected automatically from the project files);
   optionally enter a stop time such as `200ns` in the same area
4. If needed, check the GHDL and Surfer paths in Settings (button
   "Detect automatically")
5. Menu "Simulation" → "Analyze + Elaborate + Run"
6. After a successful run the view switches automatically to the "Waveforms" tab: if
   Surfer is available it is embedded automatically (may take a few seconds; the
   status is shown above the waveforms); otherwise the built-in fallback viewer
   appears immediately with a time ruler and the simulated signal traces

## Development & tests

The modules `ghdl_commands.py` and `vcd_parser.py` have no Qt dependencies and
are fully testable with `pytest` (even without GHDL installed):

```bash
pip install -r requirements-dev.txt
pytest
```

## Design choice: Python + PySide6

PySide6 (the official Qt for Python bindings) was chosen because:

- Qt looks and behaves natively on Linux, Windows and macOS
- `QProcess` provides non-blocking process control integrated into the event loop
  (important because GHDL runs can take several seconds depending on simulation length)
- Python speeds up development of parsing logic (VCD, GHDL output) and GUI code
- The LGPL licence of PySide6 allows straightforward use in proprietary projects as well

## Licence

See [LICENSE](LICENSE).
