# Repository skills

For parameter → EM → HB work, use the mandatory
[session workflow contract](../docs/guides/workflow_enforcement.md).
The submission and execution gates run automatically; the optional checkpoint
script is not a substitute. Existing running workers must not be interrupted to upgrade.

Codex skill entry points for this package:

The user prohibits treating a partial skill read as completion. Read each selected
`SKILL.md` through its end, plus the reference sections required by the operation.
`-TotalCount`, `head`, `Select -First`, search hits and remembered summaries do not
meet this requirement. If tool output is truncated, retrieve the missing contiguous
sections before any dependent model write or solve. Split large reads instead of
batching so much text that the tool drops the middle. A full-file read command alone
does not prove that its output reached the model in full.

After context compaction, if only a summary remains, reload the selected entry
points and needed reference sections before acting. Reuse complete unchanged text
still present in the current context; do not reread it mechanically on every call.
Restore the current project requirements as well. Do not ask the user to remind
you, and do not substitute a read receipt, file hash or `read=true` flag for reading.

- [cst-sessions](cst-sessions/SKILL.md): default conversation-bound persistent CST environments, recovery, and deduplication.
- [cst-in-situ-validation](cst-in-situ-validation/SKILL.md): validate and improve reusable automation during authorized engineering work.

- [cst-modeling](cst-modeling/SKILL.md)
- [cst-simulation](cst-simulation/SKILL.md)
- [cst-mesh-frequency](cst-mesh-frequency/SKILL.md): electrical-size/cost assessment, frequency sampling and mesh-adaptation decisions.
- [cst-parameter-study](cst-parameter-study/SKILL.md): linear/logarithmic/discrete native scans and server preparation.
- [cst-circuit](cst-circuit/SKILL.md): Design Studio schematics, EM links, field-circuit tasks, circuit results, and service/MCP workflows.
- [diode-isolator-design-workflow](diode-isolator-design-workflow/SKILL.md): coordinate CST EM, native zero-bias circuit SP, ADS HB and iterative analysis.
- [cst-device-characterization](cst-device-characterization/SKILL.md): device evaluation conditions, metrics, and evidence-based reporting.
- [cst-diode-loading](cst-diode-loading/SKILL.md): diode representations, bias/interface checks, parasitics, and numerical validity.
- [cst-figures](cst-figures/SKILL.md): scientific plots, geometry previews, and reproducible figure styles.
- [cst-results](cst-results/SKILL.md)
- [cst-diagnostics](cst-diagnostics/SKILL.md)

These repository-local rules preserve preview-first geometry work, real-dialog diagnosis, dependency-stage acceptance, and evidence boundaries without relying on a user-level skill installation.

For multi-turn engineering, start from the saved
[workflow checkpoint](cst-sessions/references/workflow-checkpoint.md), not a remembered
subset of the last turn. The selected task skill supplies the checks; the checkpoint
preserves current requirements, dependencies and evidence across handoffs.
When both user-level and plugin copies exist, record the chosen skill path and
runtime module path once and use that source consistently. Repository maintenance
uses this directory; plugin consumers use their installed bundle. A source edit
does not update an installed plugin or an already running worker.

Current field-circuit work prioritizes functional coverage and reusable skills. Dedicated engineering validation is deferred to actual projects; existing evidence and acceptance criteria remain in force. See [development priorities](../docs/CIRCUIT_DEVELOPMENT.md).

- [keysight-ads-simulation](keysight-ads-simulation/SKILL.md): ADS circuits, HB datasets, and CST-to-ADS Touchstone handoff.
