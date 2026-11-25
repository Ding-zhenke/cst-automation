---
name: keysight-ads-results
description: Read existing Keysight ADS .ds datasets, calculate or plot measurements, and create, inspect or open .dds Data Displays. Use when the requested output comes from saved results.
---

# Keysight ADS results and Data Display

Start from the identified dataset or display and its linked dataset. Resolve the block, signal, axes, direction, units and source run needed for the requested quantity. Existing exported CSV or JSON can be analyzed offline.

Before the first ADS import or launch, follow the [native preflight](../keysight-ads-simulation/references/environment-and-compatibility.md#mandatory-preflight) on the licensed host with `sandbox_permissions="require_escalated"`. Use the linked hidden ADS Python launcher for unattended Windows work. Before writing, inspect the destination and apply [workspace safety](../keysight-ads-simulation/references/environment-and-compatibility.md#workspace-safety).

- **Read or plot a result.** The parsed `.ds` is the source of truth for numerical acceptance. Never derive numerical values from screenshots when structured data is available. [Validate the dataset](../keysight-ads-simulation/references/dataset-and-dds.md#read-and-validate-ads-datasets) and [export calculations or plots](../keysight-ads-simulation/references/dataset-and-dds.md#export-calculations-and-plots) as requested. Report missing blocks or samples against the identified file.
- **Create a display.** [Create the DDS](../keysight-ads-simulation/references/dataset-and-dds.md#create-a-data-display-file), then [reopen and compare](../keysight-ads-simulation/references/dataset-and-dds.md#reopen-and-compare) its dataset and traces. For headless delivery, record `GUI check is not applicable`.
- **Show the native window.** Follow [native Data Display delivery](../keysight-ads-simulation/references/dataset-and-dds.md#deliver-a-native-data-display-window), verify the intended dataset and plots in that window, and leave it open.
