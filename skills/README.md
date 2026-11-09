# Repository skills

Codex skill entry points for this package:

Read the selected `SKILL.md` completely, then only the references needed for the
current operation. A `-TotalCount`/head excerpt or search hit is discovery, not
completion of the workflow instructions. On resumed work, reload the saved
requirements and any changed skill entry point before the next dependent action.

- [cst-sessions](cst-sessions/SKILL.md): default conversation-bound persistent CST environments, recovery, and deduplication.
- [cst-in-situ-validation](cst-in-situ-validation/SKILL.md): validate and improve reusable automation during authorized engineering work.

- [cst-modeling](cst-modeling/SKILL.md)
- [cst-simulation](cst-simulation/SKILL.md)
- [cst-mesh-frequency](cst-mesh-frequency/SKILL.md): electrical-size/cost assessment, frequency sampling and mesh-adaptation decisions.
- [cst-parameter-study](cst-parameter-study/SKILL.md): linear/logarithmic/discrete native scans and server preparation.
- [cst-circuit](cst-circuit/SKILL.md): Design Studio schematics, EM links, field-circuit tasks, circuit results, and service/MCP workflows.
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
