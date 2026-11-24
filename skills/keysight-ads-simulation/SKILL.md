---
name: keysight-ads-simulation
description: Build and review editable hierarchical RF schematics, circuit testbenches and synchronized physical layouts in Keysight PathWave ADS. Use for mixer, amplifier, oscillator, filter or switch simulation, optimization, LineCalc, layout EM with RFPro/Momentum, .ds datasets and .dds displays, DRC, Gerber/Drill, CAM round trips, or ADS diagnostics including fopen(NULL), a Get Started modal and exit hangs.
---

# Keysight ADS Simulation

Read this entire entry and the reference sections required by the selected operation. Recover missing text after truncation or context loss before using the native APIs.

The desktop sandbox has no access to the ADS license on this Windows
workstation. Run every native ADS operation on the approved host outside the
sandbox from the first call. For Codex shell commands, set
`sandbox_permissions="require_escalated"` on the initial invocation, including
when using the ADS Python launcher. This applies to launching ADS or Data
Display, importing ADS Python packages, probing versions or licenses, opening
workspaces, reading `.ds` or `.dds` through ADS, and running the simulator.
If host approval is unavailable, report the blocker and stop native work.
An initialization exception from a sandboxed run (including `0xE06D7363` with an empty log or
missing dataset) does not establish a circuit, model, licensing, or machine fault.
Pure source and existing JSON/text inspection can remain in the restricted context.

For unattended Windows scripts, use [the ADS Python launcher](scripts/invoke_ads_python.ps1)
in the authorized environment. It starts the bundled Python with its console
hidden and forwards stdout, stderr and the exit code. Use a visible console
when the user explicitly asks to interact with one.

For repeated CST-to-ADS work, reuse the [common operation map](../../docs/guides/reusable_operations.md)
and the official interfaces below. Opening/building/binding a supported design,
running its netlist and reading datasets do not require screenshots or GUI clicks.
Keep project-specific topology and parameters in the project, and bind each new
EM input/dataset to its actual run; older successful HB data do not certify it.

Use the ADS **official Python API** as the primary control surface and the `.ds` dataset as the source of truth for numerical acceptance. The normal evidence path is `simulate -> read .ds -> calculate -> CSV/JSON -> script plot`. Never derive numerical values from screenshots when structured ADS data is available.

Protect user work: inventory the requested root first, create unique workspace and run-output paths, and **never overwrite** an existing workspace, dataset, display, netlist, log, layout, or fabrication export unless the user explicitly authorizes that exact replacement.

## Build an editable ADS project

For a multi-block circuit, follow the [hierarchical schematic and placement guide](references/hierarchical-schematic.md) from reusable cells and symbols through the assembled device to its testbenches. Apply the placement and parameter-display checks inside each child as well as on the top sheet.

For a project with layout simulation, continue from the selected circuit dimensions through [layout synchronization and Momentum](references/layout-em-and-fabrication.md#synchronize-the-circuit-candidate-before-layout-em). Deliver the physical view, its port map and the requested EM result. For a setup-only request, deliver the configuration and identify the pending solve. A presentation-only edit ends with the saved schematic and its netlist comparison.

## HB RF-frequency sweeps

Prefer ADS native HB sweeps: one simulator invocation per fixed pump/bias/state
and excitation direction, with all requested RF frequencies swept inside ADS.
Do not restart the simulator for every RF point. Read the
[native HB sweep contract](references/nonlinear-rf-workflows.md#native-hb-rf-frequency-sweeps)
before planning an HB frequency scan; it covers controller settings, sweep counts,
finite-power analysis, coincident mixing products and justified pointwise fallbacks.

## Select the validation level

- `flow` is the default. Prove the requested build and solver path with the smallest useful run, inspect the resulting database/netlist/dataset directly, and report measured values without imposing an unstated performance specification.
- `release` is explicit. Add user-defined performance thresholds and tolerances, wider sweeps or state coverage, reopen/rerun reproducibility, and the applicable physical-design release gates. Do not silently promote a flow check into release acceptance.

Build, solver, and performance are independent gates. A valid schematic or layout does not prove that a solver completed; a completed solver does not prove that an RF specification passed. If an applicable gate was not executed, mark it `not verified`.

## Load only the relevant guidance

- Always read [environment-and-compatibility.md](references/environment-and-compatibility.md) before importing an ADS package.
- Read [design-and-simulation.md](references/design-and-simulation.md) before creating or changing a workspace, schematic, simulation controller, layout generated from a schematic, EM co-simulation view, or netlist.
- To display an editable schematic, use the [native desktop window API](references/design-and-simulation.md#open-an-editable-schematic-in-desktop-ads) inside the target ADS session and verify the returned window.
- Read [linear-rf-workflows.md](references/linear-rf-workflows.md) for an amplifier, filter, or RF switch, including DC, S-parameter, state-sweep, and circuit-to-Momentum comparisons.
- Read [nonlinear-rf-workflows.md](references/nonlinear-rf-workflows.md) for a mixer or oscillator, including harmonic balance, spectral products, oscillator search, and phase noise.
- Read [dataset-and-dds.md](references/dataset-and-dds.md) before accepting a `.ds` result or creating or inspecting a `.dds` display.
- Read [layout-em-and-fabrication.md](references/layout-em-and-fabrication.md) for PCB layout, substrate, padstack, via, Momentum/RFPro, DVE DRC, Gerber/Drill export, or CAM round-trip work. Its `flow` and `release` gates are intentionally different.
- Read [troubleshooting.md](references/troubleshooting.md) for startup, licensing, convergence, library, model, topology, or simulator errors.
- Read [ads-agent-bridge.md](references/ads-agent-bridge.md) when using or repairing ADS Agent Bridge, including ADS 2025 compatibility and per-machine setup.
- Use [official-doc-index.md](references/official-doc-index.md) to locate the installed ADS 2026 Update 1 pages and examples. Verify component identifiers and parameter names against that installed release.

## Execute the common RF workflow

1. Resolve scope, validation level, inputs, and a new output root. For a physical design, follow the layout and EM stages above. The steps below cover the circuit testbench. Record the intended circuit family, analysis, model/PDK dependencies, frequencies or sweep axes, terminations, requested outputs, and any explicit acceptance limits.
2. Run capability-scoped preflight. Set `HPEESOF_DIR` before ADS imports, choose the ADS-bundled interpreter or a compatible environment, and record ADS, DE API, Python, simulator, import, and license evidence.
3. Build through `keysight.ads.de` and `db_uu`. Save the design, verify instance definitions and `instance.parameters`, generate the netlist, and inspect component models, values, pins, connectivity, ports, sources, and controller settings.
4. Prefer `keysight.edatoolbox.ads.CircuitSimulator.run_netlist` with a dedicated output directory. Retain the exact netlist and combined log, and classify the actual process result; direct `hpeesofsim` is a documented fallback or diagnostic route. Before using the bundled runner, read its [working-directory and inventory limits](references/design-and-simulation.md#run-and-preserve-solver-evidence); its `ok` status does not replace the numerical checks in step 5.
5. Open the current `.ds` with `keysight.ads.dataset`, enumerate blocks and axes, select the requested signal by identity, and verify finite values, expected points, solver status, and absence of fatal or license errors. Dataset existence alone is not success.
6. Generate CSV/JSON and noninteractive plots from the same parsed data when review artifacts are requested. Record formulas, units, conventions, paths, and hashes.
7. Add only the checks required by the selected circuit-family reference and validation level. Keep circuit, layout, EM, fabrication, and performance verdicts separate.

Prefer relative paths for files referenced by generated ADS netlists, especially
when the workspace path contains Chinese characters. In one observed failure,
ADS could not parse a netlist containing a Chinese absolute path; changing the
reference to a relative path resolved it. Run with a known working directory
and verify that each relative reference resolves from there. If parsing fails,
preserve the failing netlist and full failure log before making a path change so
the cause remains inspectable.

Create or inspect DDS only when the user requests it or the deliverable requires a Data Display. A request for native Data Display windows requires opening the saved `.dds` in the visible ADS Data Display application, checking the intended dataset and plots in the window, and leaving the window open for the user. Follow the [native window workflow](references/dataset-and-dds.md#deliver-a-native-data-display-window). For headless deliverables, use programmatic reopen, structural inspection, and agreement with the independently parsed `.ds`. Record `GUI check is not applicable` for a headless delivery.

Preserve warnings, model limitations, and fatal errors as distinct evidence. Behavioral or ideal models support only the claims their parameters justify; they do not turn simulated performance into a hardware guarantee.

For CST EM Touchstone to ADS nonlinear circuit handoff, read [CST to ADS handoff](references/cst-ads-bridge.md).
