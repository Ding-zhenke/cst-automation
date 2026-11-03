---
name: cst-simulation
description: Configure and run CST electromagnetic simulations on an existing, reviewed project using cst_solver or tpc_service.
---

# CST simulation

Before choosing mesh/frequency settings, use
[cst-mesh-frequency](../cst-mesh-frequency/SKILL.md) to estimate electrical size
and select automatic or representative-point adaptation. For native ranges and
server scans use [cst-parameter-study](../cst-parameter-study/SKILL.md).

For actual Codex operations, first apply [persistent conversation sessions](../cst-sessions/SKILL.md).
For server scan preparation, use [the project lifecycle](../cst-sessions/references/project-lifecycle.md):
configure the original project without starting a solve, check corners in place,
restore defaults, and retain the final file with its modeling Python. Use session
`configure_sweep` for linear/logarithmic/discrete axes; do not produce per-corner backup projects.

For Design Studio schematics, EM links, or field-circuit tasks, use [cst-circuit](../cst-circuit/SKILL.md). Its current development scope prioritizes functions and skills; do not start dedicated validation solves unless required by the user's engineering task.

Confirm the target project, solver type, frequency range, ports, boundaries, mesh, and requested outputs before starting a costly solve. Reuse the accepted geometry; do not silently rebuild or replace a user's project. Use `run_checked`/the service run contract, save before reading results, and report the exact run identity and status.

For reviewed transient EM projects, `app.configure_em_time_settings(settings)` sets a sparse `stability_factor` in `(0,1]` and/or `output_sampling="every_step"/"automatic"`. It submits history only, without reset, rebuild, save, DS changes, external-link edits, or solving. Save explicitly. Requested factor and history submission do not establish actual integration timestep or every-step output: native readback is unsupported and verification flags stay False. See the [time-control guide](../../docs/guides/circuit_cosimulation.md#em-时间步与每步输出配置). Do not start validation solves when the user requests offline work only.

Inspect real CST dialogs when an SDK call stalls. A timeout, open dialog, or closed dialog is not solver success. Keep offline/fake backend evidence separate from CST execution. Do not infer isolation, topology, or device performance from a successful solver return alone.

See [the CST API](../../docs/packages/cst_solver.md), [dialog procedure](../../docs/guides/cst_dialogs.md), and [troubleshooting](../../docs/guides/troubleshooting.md).

## Sweep sampling and F-solver mesh decisions

For parameter studies, choose linear, logarithmic or explicit discrete sampling
using `configure_sweep`; consult the [sampling contract](../../docs/PUBLIC_API.md#native-linear-logarithmic-and-discrete-parameter-sweeps).
Do not default every range to arbitrary points. Keep zero states separate from
positive logarithmic ranges. Frequency samples, interpolated output points,
mesh adaptation frequencies, and parameter cases are separate settings.

For the tetrahedral F solver, explicitly review the global material-wavelength
mesh, local gaps/thin layers, adaptation frequency and pass/Delta-S criteria.
Do not refine the whole device to the smallest local feature size. After mesh
adaptation, reuse that mesh for the broadband frequency sampling of that case;
do not request adaptation at every plotted output point. Across parameter
cases, distinguish geometry changes from material-only changes: geometry can
invalidate a mesh, while material changes can invalidate the previous solution
or its error indicator. Only enable cross-case reuse when supported and checked.
Report actual cells/DOF only when meshing has been performed; configured limits
are not convergence evidence. This guidance specifies decisions, not a claim
that the current general mesh wrappers cover every F-solver setting.
