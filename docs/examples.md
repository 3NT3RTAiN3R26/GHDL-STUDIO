# Examples

Both examples ship under [`examples/`](https://github.com/3NT3RTAiN3R26/GHDL-STUDIO/tree/main/examples)
in the repository.

## Counter (Normal mode)

Files: `counter.vhd`, `counter_tb.vhd`

1. Start in **Normal GHDL** mode
2. **Project files → Add file…** — add `counter.vhd`, then `counter_tb.vhd`
3. Set **Top-level entity** to `counter_tb`, optional stop time `200ns`
4. **Simulation → Analyze + Elaborate + Run**
5. Inspect **Waveforms**

![Counter project in Normal mode](images/docs_normal_mode.png){ width="900" }

## Adder (OSVVM)

| File | Role |
|------|------|
| `adder.vhd` | DUT |
| `adder_tb.vhd` | OSVVM AffirmIfEqual testbench |
| `adder.pro` | OSVVM Scripts build |

### Via OSVVM mode

1. Configure TCL + OSVVM Scripts path in Settings
2. Choose **OSVVM mode** and select `examples/adder/adder.pro`
3. Optionally add further `.pro` files and check the active one
4. **Build .pro (OSVVM)**

![OSVVM adder.pro workspace](images/docs_osvvm_mode.png){ width="900" }

Successful build (13 affirmations):

![Build PASSED](images/adder_osvvm_run.png){ width="900" }

### Via Normal mode + `-P`

1. **Precompile OSVVM library…** (or point **OSVVM lib path** at an existing `VHDL_LIBS/GHDL-*`)
2. Add `adder.vhd` then `adder_tb.vhd`
3. Top-level `adder_tb` → Analyze → Elaborate → Run
