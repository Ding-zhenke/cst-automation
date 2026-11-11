---
name: keysight-ads-simulation
description: Use when working with Keysight PathWave ADS RF circuits or physical designs, including mixer, amplifier, oscillator, filter, RF switch, schematic, PCB layout, LineCalc transmission-line synthesis, Momentum or RFPro EM, DRC, Gerber, Drill, CAM round trips, .ds datasets, .dds displays, netlists, simulation logs, licenses, reproducibility checks, or ADS application-mode failures such as fopen(NULL), a Get Started modal, or exit hangs.
---

# Keysight ADS Simulation

Use the ADS **official Python API** as the primary control surface and the `.ds` dataset as the source of truth for numerical acceptance. The normal evidence path is `simulate -> read .ds -> calculate -> CSV/JSON -> script plot`. Never derive numerical values from screenshots when structured ADS data is available.

Protect user work: inventory the requested root first, create unique workspace and run-output paths, and **never overwrite** an existing workspace, dataset, display, netlist, log, layout, or fabrication export unless the user explicitly authorizes that exact replacement.

## Select the validation level

- `flow` is the default. Prove the requested build and solver path with the smallest useful run, inspect the resulting database/netlist/dataset directly, and report measured values without imposing an unstated performance specification.
- `release` is explicit. Add user-defined performance thresholds and tolerances, wider sweeps or state coverage, reopen/rerun reproducibility, and the applicable physical-design release gates. Do not silently promote a flow check into release acceptance.

Build, solver, and performance are independent gates. A valid schematic or layout does not prove that a solver completed; a completed solver does not prove that an RF specification passed. If an applicable gate was not executed, mark it `not verified`.

## Load only the relevant guidance

- Always read [environment-and-compatibility.md](references/environment-and-compatibility.md) before importing an ADS package.
- Read [design-and-simulation.md](references/design-and-simulation.md) before creating or changing a workspace, schematic, simulation controller, layout generated from a schematic, EM co-simulation view, or netlist.
- Read [linear-rf-workflows.md](references/linear-rf-workflows.md) for an amplifier, filter, or RF switch, including DC, S-parameter, state-sweep, and circuit-to-Momentum comparisons.
- Read [nonlinear-rf-workflows.md](references/nonlinear-rf-workflows.md) for a mixer or oscillator, including harmonic balance, spectral products, oscillator search, and phase noise.
- Read [dataset-and-dds.md](references/dataset-and-dds.md) before accepting a `.ds` result or creating or inspecting a `.dds` display.
- Read [layout-em-and-fabrication.md](references/layout-em-and-fabrication.md) for PCB layout, substrate, padstack, via, Momentum/RFPro, DVE DRC, Gerber/Drill export, or CAM round-trip work. Its `flow` and `release` gates are intentionally different.
- Read [troubleshooting.md](references/troubleshooting.md) for startup, licensing, convergence, library, model, topology, or simulator errors.
- Use [official-doc-index.md](references/official-doc-index.md) to locate the installed ADS 2026 Update 1 pages and examples. Verify component identifiers and parameter names against that installed release.

## Execute the common RF workflow

1. Resolve scope, validation level, inputs, and a new output root. Record the intended circuit family, analysis, model/PDK dependencies, frequencies or sweep axes, terminations, requested outputs, and any explicit acceptance limits.
2. Run capability-scoped preflight. Set `HPEESOF_DIR` before ADS imports, choose the ADS-bundled interpreter or a compatible environment, and record ADS, DE API, Python, simulator, import, and license evidence.
3. Build through `keysight.ads.de` and `db_uu`. Save the design, verify instance definitions and `instance.parameters`, generate the netlist, and inspect component models, values, pins, connectivity, ports, sources, and controller settings.
4. Prefer `keysight.edatoolbox.ads.CircuitSimulator.run_netlist` with a dedicated output directory. Retain the exact netlist and combined log, and classify the actual process result; direct `hpeesofsim` is a documented fallback or diagnostic route.
5. Open the current `.ds` with `keysight.ads.dataset`, enumerate blocks and axes, select the requested signal by identity, and verify finite values, expected points, solver status, and absence of fatal or license errors. Dataset existence alone is not success.
6. Generate CSV/JSON and noninteractive plots from the same parsed data when review artifacts are requested. Record formulas, units, conventions, paths, and hashes.
7. Add only the checks required by the selected circuit-family reference and validation level. Keep circuit, layout, EM, fabrication, and performance verdicts separate.

Create or inspect DDS only when the user requests it or the deliverable requires a Data Display. Programmatic reopen, structural inspection, and agreement with the independently parsed `.ds` are sufficient for headless validation. When the user did not request visible UI verification, report exactly `GUI check is not applicable`.

Preserve warnings, model limitations, and fatal errors as distinct evidence. Behavioral or ideal models support only the claims their parameters justify; they do not turn simulated performance into a hardware guarantee.

For CST EM Touchstone to ADS nonlinear circuit handoff, read [CST to ADS handoff](references/cst-ads-bridge.md).
