---
name: keysight-ads-simulation
description: Configure or run Keysight ADS circuit analyses and optimization, including DC, SP and native HB sweeps. Select for controller setup, solver execution or diagnosing a circuit run.
---

# Keysight ADS circuit simulation

Identify the testbench, requested analysis, excitation, sweep axes and intended deliverable. For setup only, save and verify the controller, sources and emitted netlist, then finish. For an authorized run, deliver the exact netlist, log, current dataset and requested measurements.

Before the first ADS import or launch, follow the [native preflight](references/environment-and-compatibility.md#mandatory-preflight) on the licensed host with `sandbox_permissions="require_escalated"`. Use the linked hidden ADS Python launcher for unattended Windows work. Before writing, inspect the destination and apply [workspace safety](references/environment-and-compatibility.md#workspace-safety).

- **Configure a testbench.** Use the official Python API and [select the analysis from the measurement](references/design-and-simulation.md#select-the-analysis-from-the-measurement). For amplifier, filter or RF switch studies, read the common contract and matching section of [linear RF workflows](references/linear-rf-workflows.md). For mixer or oscillator analyses, use the corresponding sections of [nonlinear RF workflows](references/nonlinear-rf-workflows.md).
- **Sweep HB frequency.** Read [native HB RF-frequency sweeps](references/nonlinear-rf-workflows.md#native-hb-rf-frequency-sweeps). Sweep the requested RF axis inside ADS for each fixed pump, bias, state and excitation direction. Report simulator invocations and frequency points separately.
- **Run and verify.** Follow [run and preserve solver evidence](references/design-and-simulation.md#run-and-preserve-solver-evidence). Resolve relative model and SNP paths from the actual working directory. Write new outputs to a dedicated directory. Check simulator status and log, then [validate the requested dependent signals and all sweep axes](references/dataset-and-dds.md#read-and-validate-ads-datasets). The default `flow` reports measured values. For explicit `release`, apply the requested limits, coverage and [reproducibility checks](references/design-and-simulation.md#release-reopen-and-reproducibility).
- **Conditional inputs and failures.** For a CST network, verify the exact run, port map and input file using [CST to ADS handoff](references/cst-ads-bridge.md). For a failed run, read the matching [troubleshooting section](references/troubleshooting.md). For release-specific identifiers use the [installed documentation index](references/official-doc-index.md).

For requests using this skill's former broad name, select the requested deliverable directly: [editable schematic or parameter change](../keysight-ads-schematic/SKILL.md), [saved dataset or display](../keysight-ads-results/SKILL.md), or [layout, EM or fabrication](../keysight-ads-layout/SKILL.md).
