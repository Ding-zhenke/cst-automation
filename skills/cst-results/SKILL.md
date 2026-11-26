---
name: cst-results
description: Read and analyze exported files or saved CST results. Use for existing curves, result-tree data, or per-Run-ID Touchstone files from a completed EM parameter sweep.
---

# Read or export existing CST results

Select the source and requested output. For exported CSV, JSON, Touchstone or text logs, read the file in the sandbox. Preserve the recorded axes, units, port order and case identity.

For native data, use the licensed host from the first `cst.results` or `cst_solver.Result` import with `sandbox_permissions="require_escalated"`. Run unattended Windows Python through the [hidden launcher](../keysight-ads-simulation/scripts/invoke_hidden.ps1) for both native and file-only work.

- **Read a saved result.** Select the project, result domain, tree item and explicit Run ID. Report the requested values, units, conversion and source. If the item is missing, report its path and Run ID. A saved project can be read without starting a Design Environment. Use the [owning session](../cst-sessions/SKILL.md) for a live project read.
- **Export a saved EM sweep.** Follow [per-Run-ID Touchstone export](references/exports-and-history.md#exporting-em-sweep-points-as-touchstone-files). Match the manifest to the requested parameter combinations and deliver the files with their port map, reference impedance and frequency unit.
- **Export 2D/3D field data.** Check the existing `setup.export_field` / `export_result_2d3d` implementations and the owning session's export capabilities. The former prefixes `2D/3D Results`; the latter accepts a full tree path. Neither proves the required complex components were exported. Missing routing calls for a dedicated export operation, not a geometry batch that rebuilds the model. If unavailable in the current worker, a bounded UI export may use the confirmed owning DE and project while idle; preserve the session identity and identify the gap. Check the output header, coordinates, units and requested complex components. Reuse established export settings across cases instead of rediscovering them in the UI.
- **Measure bands or resonances.** Use the shared `cst_automation.curves` rules for contiguous bands and sampled resonances. Report derived measurements with the source curves.

For a frozen project or a cache-retention check, follow the [noninteractive frozen-package read procedure](../../docs/guides/reusable_operations.md#从冻结副本读曲线). Before a parameter rerun or a history comparison, read [parameter-study history](references/exports-and-history.md#parameter-study-history). For bad-element attribution, use the [warning snapshot and native ID checks](../../docs/guides/reusable_operations.md#告警网格快照与归因).

For an automatic export step in the project, use [CST result templates](../cst-result-templates/SKILL.md). For reader interfaces, consult the matching [result API](../../docs/packages/cst_solver.md) or [Python example](../../docs/guides/python-usage.md).
