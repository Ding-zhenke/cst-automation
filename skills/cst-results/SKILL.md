---
name: cst-results
description: Read, export, and analyze CST result trees, fields, far fields, or S-parameter curves while preserving run identity and evidence boundaries.
---

读完本入口和当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

# CST results

Read native CST results on the approved host from the first SDK import. For
Codex command tools, set `sandbox_permissions="require_escalated"` on the first
command using `cst.results` or `cst_solver.Result`, including noninteractive
reads of saved or frozen projects. Parsing already exported CSV, JSON,
Touchstone or text logs without the CST SDK can run in the sandbox.
For either path, use the [hidden launcher](../keysight-ads-simulation/scripts/invoke_hidden.ps1)
for noninteractive Windows Python commands.

For low-quality mesh warnings, preserve the original bad-element files together
with their mesh and material mapping before another pass replaces them. Read
[warning snapshots and attribution](../../docs/guides/reusable_operations.md#告警网格快照与归因).
Only assign materials/locations after independently matching native IDs and
reconstructed quality; a final mesh cannot silently replace the warning's mesh.
Keep capture stability, mapping validity and solver/convergence claims separate.

For immutable diagnostics, read the [freeze/read contract](../../docs/guides/reusable_operations.md#冻结读取及有效网格输入).
Use official `cst.results.ProjectFile(frozen_path, allow_interactive=False)` on the
verified frozen package; current `cst_solver.Result` defaults to interactive reads.
Do not fallback to the live DE, alias 0 or an old positive ID on failure. Preserve
all requested matrix elements and axes. A short diagnostic never qualifies full EM.
After a cache-choice dialog, verify retained matrices from a complete saved copy
frozen before the next solve. A noninteractive refusal on the still-open original
project is not data loss or cache success; preserve it and do not switch to interactive.

Online CST reads must use [the conversation's persistent session](../cst-sessions/SKILL.md).
Saved-project SDK reads can run on the host without a DE. Preserve the session's explicit saved project/run identity.

Use the saved project and explicit run ID with `cst_solver.Result`/result helpers. Report which tree item and run were read, units and conversion convention, and any read errors. If a result is absent, return that failure rather than substituting an empty curve or an older run.

A positive native run ID can identify a parameter state and be reused or overwritten
when that state is solved again, including mesh reruns. An explicit ID selects data;
it does not freeze an execution. Before a rerun, preserve required complete complex
results, native logs and parameters with project/result content hashes in the task's
existing archive. Keep execution identity separate from the native parameter-state ID.

The shared `cst_automation.curves` module defines the only contiguous-band and sampled-resonance rules; use it rather than writing a second threshold implementation. Result extraction proves data was read, not that a solve was run in this session or that a device meets a performance claim. Preserve solver output, readback, and interpretation as separate evidence.

See [result APIs](../../docs/packages/cst_solver.md) and [Python examples](../../docs/guides/python-usage.md).

## Export and history

- To export a saved EM sweep, read [Touchstone export](references/exports-and-history.md#exporting-em-sweep-points-as-touchstone-files). Confirm the complete complex matrix, positive native Run ID and stored parameters, reference impedance and output identity for each case. An export reads existing results.
- Before a parameter rerun or an EM/HB history comparison, read [parameter-study history](references/exports-and-history.md#parameter-study-history). Preserve complete complex data and logs before updates, and verify the requested parameter association and save/reopen persistence.
