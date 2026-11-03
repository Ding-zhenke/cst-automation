---
name: cst-results
description: Read, export, and analyze CST result trees, fields, far fields, or S-parameter curves while preserving run identity and evidence boundaries.
---

# CST results

Online CST reads must use [the conversation's persistent session](../cst-sessions/SKILL.md).
Offline Result file reads need no DE; still preserve the session's explicit saved project/run identity.

Use the saved project and explicit run ID with `cst_solver.Result`/result helpers. Report which tree item and run were read, units and conversion convention, and any read errors. If a result is absent, return that failure rather than substituting an empty curve or an older run.

The shared `cst_automation.curves` module defines the only contiguous-band and sampled-resonance rules; use it rather than writing a second threshold implementation. Result extraction proves data was read, not that a solve was run in this session or that a device meets a performance claim. Preserve solver output, readback, and interpretation as separate evidence.

See [result APIs](../../docs/packages/cst_solver.md) and [Python examples](../../docs/guides/python-usage.md).

## Parameter-study history

Use `cst_solver.circuit.StudyResult(batch_path)` for immutable per-case snapshots, parameter filtering, complex curve reads and component comparisons. Preserve case status and source EM/circuit evidence; the source run 0 is metadata, not a stable historical handle. Native summaries are grouped under Results/Studies by batch/result/component/case. `verify_project()` checks saved native leaves against archived arrays without closing/reopening CST; report saved_readback_verified separately from native reopen acceptance. Keep the project result directory with the .cst until single-file packaging has been verified. See [parameter studies](../../docs/guides/circuit_parameter_studies.md).
