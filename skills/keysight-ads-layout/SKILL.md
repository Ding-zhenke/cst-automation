---
name: keysight-ads-layout
description: Create or synchronize physical layouts in Keysight ADS, size lines with LineCalc, configure or run Momentum/RFPro, check DRC, or deliver Gerber and Drill files.
---

# Keysight ADS layout, EM and fabrication

Identify the source cell or physical layout, stackup, units, ports and requested output. For a circuit-derived layout, [synchronize the selected dimensions and port map](../keysight-ads-simulation/references/layout-em-and-fabrication.md#synchronize-the-circuit-candidate-before-layout-em). Start from the supplied physical view for layout-only work.

Before the first ADS import or launch, follow the [native preflight](../keysight-ads-simulation/references/environment-and-compatibility.md#mandatory-preflight) on the licensed host with `sandbox_permissions="require_escalated"`. Use the linked hidden ADS Python launcher for unattended Windows work. Before writing, inspect the destination and apply [workspace safety](../keysight-ads-simulation/references/environment-and-compatibility.md#workspace-safety).

Resolve the reference's `scripts/` paths under the sibling `keysight-ads-simulation/` directory.

| Requested output | Read and finish at |
|---|---|
| Line dimensions or editable layout | Use [LineCalc](../keysight-ads-simulation/references/layout-em-and-fabrication.md#synthesize-controlled-impedance-lines-with-linecalc) for controlled impedance or [physical layout checks](../keysight-ads-simulation/references/layout-em-and-fabrication.md#create-and-inspect-a-physical-layout) for geometry, nets, layer purposes and ports. |
| EM configuration or results | Follow [RFPro/Momentum](../keysight-ads-simulation/references/layout-em-and-fabrication.md#run-rfpromomentum). For setup, save and verify the substrate, ports, mesh and sweep. For a requested solve, also verify the resulting network and frequency coverage. |
| Fabrication checks or files | Use [DVE DRC](../keysight-ads-simulation/references/layout-em-and-fabrication.md#run-dve-drc-in-the-full-ads-application), [Gerber/Drill export](../keysight-ads-simulation/references/layout-em-and-fabrication.md#export-gerber-and-drill), or [CAM round-trip verification](../keysight-ads-simulation/references/layout-em-and-fabrication.md#import-and-verify-the-cam-round-trip) according to the deliverable. For release, apply the [physical release gates](../keysight-ads-simulation/references/layout-em-and-fabrication.md#select-flow-or-release). |
