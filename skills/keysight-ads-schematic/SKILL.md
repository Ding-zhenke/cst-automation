---
name: keysight-ads-schematic
description: Create, edit, open or review editable Keysight ADS schematics, hierarchical cells and instance parameters. Use for copying static values to an HB schematic for manual tuning.
---

# Keysight ADS schematics

Identify the workspace, library, cell and view. For an existing design, read its current values and units. When copying static parameters into an HB testbench, read both designs, map the requested parameters, and preserve the target's pump, bias, sources and sweep settings unless explicitly selected for editing.

Before the first ADS import or launch, follow the [native preflight](../keysight-ads-simulation/references/environment-and-compatibility.md#mandatory-preflight) on the licensed host with `sandbox_permissions="require_escalated"`. Use the linked hidden ADS Python launcher for unattended Windows work. Before writing, inspect the destination and apply [workspace safety](../keysight-ads-simulation/references/environment-and-compatibility.md#workspace-safety).

Use the [Design Environment API and parameter checks](../keysight-ads-simulation/references/design-and-simulation.md#build-with-the-design-environment-api). For a parameter inherited from a shared cell or variable, locate its owner and use the target instance override where supported. Edit the identified design in place when requested. Use the workspace creation steps for a new project. Save, read back instance parameters and compare the generated netlist against the intended changes. For manual tuning, that saved editable design completes the task.

For assemblies with reusable cells, follow [hierarchy, placement and visible wiring](../keysight-ads-simulation/references/hierarchical-schematic.md) on the child and top sheets. When the user requests an open schematic window, use the [desktop window API](../keysight-ads-simulation/references/design-and-simulation.md#open-an-editable-schematic-in-desktop-ads), verify the returned context and leave the window open. Read the [Agent Bridge guide](../keysight-ads-simulation/references/ads-agent-bridge.md) when using or repairing that bridge.
