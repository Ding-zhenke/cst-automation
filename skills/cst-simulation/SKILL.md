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

F-solver CPU parallelization uses `configure_fd_parallelization(settings)` through
the existing session `model_api`: boolean `enabled`, positive integer `threads`
and `cpu_devices` (sockets), with omitted fields preserved. Use explicit enabled=True
to turn it on; do not substitute transient `set_parallel_threads` or DS HB settings.
The receipt records configuration only; verify actual threads from the native run log.
This interface does not configure GPU acceleration or choose a different solver.

For reviewed transient EM projects, `app.configure_em_time_settings(settings)` sets a sparse `stability_factor` in `(0,1]` and/or `output_sampling="every_step"/"automatic"`. It submits history only, without reset, rebuild, save, DS changes, external-link edits, or solving. Save explicitly. Requested factor and history submission do not establish actual integration timestep or every-step output: native readback is unsupported and verification flags stay False. See the [time-control guide](../../docs/guides/circuit_cosimulation.md#em-时间步与每步输出配置). Do not start validation solves when the user requests offline work only.

Inspect real CST dialogs when an SDK call stalls. A timeout, open dialog, or closed dialog is not solver success. Keep offline/fake backend evidence separate from CST execution. Do not infer isolation, topology, or device performance from a successful solver return alone.

See [the CST API](../../docs/packages/cst_solver.md), [dialog procedure](../../docs/guides/cst_dialogs.md), and [troubleshooting](../../docs/guides/troubleshooting.md).

## 线性求解残差的有界回退

- 本规则用于未另行要求不可放宽精度的已授权求解。目标相对残差 `1e-7` 无法达到，且已排除工程/几何错误、缺失端口和不明提交后，可仅对未通过的工况放宽一次到 `1e-6`；同一授权内直接接续，不反复索取确认。用户指定更严格门槛或仅允许某个频点时，以该限制为准，不自动推广到整段或其他工况，也不继续自动放宽到 `1e-5`。
- 使用 `1e-7`、`1e-6` 或 `1×10⁻⁷`、`1×10⁻⁶`，避免 `10e-7` 这类与十次幂混淆的写法。相对残差不是 S 参数误差；不得因此降低矩阵质量、实际低频采样、拟合、无源性、互易性或网格/结果收敛验收。
- 重试前确认旧求解已结束，保全原生失败日志、参数和提交标记；不强杀或并行重交未知任务，不重算已通过频点。复用数据须保留各自原生运行身份、矩阵和日志来源，不拼接成虚假的单次运行。
- 重试使用有界迭代/运行预算；仍未达到 `1e-6` 就停止并诊断，不盲目循环。验收依据本次日志中的全部实际激励残差与结果矩阵，剔分追加日志中的旧运行，不把历史错误误判为本次失败，也不把有争议的接口状态改写成 SUCCESS。
- 报告实际用时、最大残差、迭代次数、采用的门槛和验收范围；满足条件即推进既有授权的后续阶段，单点通过不等于全扫通过。

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
