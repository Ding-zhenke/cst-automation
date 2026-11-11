---
name: cst-results
description: Read, export, and analyze CST result trees, fields, far fields, or S-parameter curves while preserving run identity and evidence boundaries.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# CST results

For immutable diagnostics, read the [freeze/read contract](../../docs/guides/reusable_operations.md#冻结读取及有效网格输入).
Use official `cst.results.ProjectFile(frozen_path, allow_interactive=False)` on the
verified frozen package; current `cst_solver.Result` defaults to interactive reads.
Do not fallback to the live DE, alias 0 or an old positive ID on failure. Preserve
all requested matrix elements and axes. A short diagnostic never qualifies full EM.

Online CST reads must use [the conversation's persistent session](../cst-sessions/SKILL.md).
Offline Result file reads need no DE; still preserve the session's explicit saved project/run identity.

Use the saved project and explicit run ID with `cst_solver.Result`/result helpers. Report which tree item and run were read, units and conversion convention, and any read errors. If a result is absent, return that failure rather than substituting an empty curve or an older run.

A positive native run ID can identify a parameter state and be reused or overwritten
when that state is solved again, including mesh reruns. An explicit ID selects data;
it does not freeze an execution. Before a rerun, preserve required complete complex
results, native logs and parameters with project/result content hashes in the task's
existing archive. Keep execution identity separate from the native parameter-state ID.

The shared `cst_automation.curves` module defines the only contiguous-band and sampled-resonance rules; use it rather than writing a second threshold implementation. Result extraction proves data was read, not that a solve was run in this session or that a device meets a performance claim. Preserve solver output, readback, and interpretation as separate evidence.

See [result APIs](../../docs/packages/cst_solver.md) and [Python examples](../../docs/guides/python-usage.md).

## Parameter-study history

For sequential EM points, `set_parameters` → `app.update()` (session-owned) →
`solve` is distinct from a native Parameter Sweep. Do not call full `Rebuild`
after the parameter update: CST documents that it deletes all results. For
acceptance check two geometry parameter combinations and all four complex S
leaves with positive 3D IDs and their actual parameter combinations, both before
and after native save/close/reopen. A successful SDK update alone is not proof
of persistence; retain independent per-case complex exports and logs.

For manual EM parameter changes followed by EM/HB reruns, require the bound native
postprocessor to regenerate the matching curves automatically and retain curves for
other parameter combinations. Verify HB storage, derived-result association and
Navigator comparison separately. One positive ID or a missing parameter legend does
not prove storage is off. Until native association is verified, automatically write
unique per-parameter Results snapshots with complete complex archives; never replace
one shared leaf across parameters. See [automatic refresh and parameter history](../../docs/guides/hb_parametric_storage_and_length_results.md)
for setting gaps, fallback and two-combination/save-reopen acceptance. Do not modify
an active scan or report offline checks as end-to-end native acceptance.

Use `cst_solver.circuit.StudyResult(batch_path)` for immutable per-case snapshots, parameter filtering, complex curve reads and component comparisons. Preserve case status and source EM/circuit evidence; the source run 0 is metadata, not a stable historical handle. Native summaries are grouped under Results/Studies by batch/result/component/case. `verify_project()` checks saved native leaves against archived arrays without closing/reopening CST; report saved_readback_verified separately from native reopen acceptance. Keep the project result directory with the .cst until single-file packaging has been verified. See [parameter studies](../../docs/guides/circuit_parameter_studies.md).
