---
name: cst-results
description: Read, export, and analyze CST result trees, fields, far fields, or S-parameter curves while preserving run identity and evidence boundaries.
---

# CST results

Use the saved project and explicit run ID with `cst_solver.Result`/result helpers. Report which tree item and run were read, units and conversion convention, and any read errors. If a result is absent, return that failure rather than substituting an empty curve or an older run.

The shared `cst_automation.curves` module defines the only contiguous-band and sampled-resonance rules; use it rather than writing a second threshold implementation. Result extraction proves data was read, not that a solve was run in this session or that a device meets a performance claim. Preserve solver output, readback, and interpretation as separate evidence.

See [result APIs](../../docs/packages/cst_solver.md) and [Python examples](../../docs/guides/python-usage.md).
