---
name: cst-simulation
description: Configure and run CST electromagnetic simulations on an existing, reviewed project using cst_solver or tpc_service.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# CST simulation

当用户明确要求本轮优先推进并豁免指定的非关键设置读回时，将这些字段及
下发记录列为 `warning / 未独立读回`，继续已授权的 EM，不为补 getter、截图
或重启 worker 延迟本轮。当前七管任务的明确豁免包括 Direct 选择、残差精度、
局部网格、自适应和完整频率表的启动前原生读回；它们不因此成为已验证设置。
该豁免仅适用于用户指定的本轮和字段，不永久取消其他约束，也不证明收敛或
频率覆盖。仍核对工程身份、参数、保存状态、用户授权和未知任务/写入状态；
提交后按实际日志、结果和可用证据报告，缺项保留未验证。

原生会话的参数修改和 EM 求解必须先绑定[工程规格](../../docs/guides/workflow_enforcement.md)。
参数更新正常成功后提交 EM；若原更新因监测或几何验证而失败，先按下列
“已审阅保存基线”规则核对，再决定是否继续，不重复写入同一参数；完成 EM 后提交关联本次回执和原始文件的数值报告，
由服务检查后才可继续 HB。绑定工程暂不支持原生 EM 扫参配置或非托管 study，
以下原生扫参建议不构成绕过该限制的许可。

正常返回保存但有原生警告的 EM，可按 [探索性保存结果证据](../../docs/guides/saved_em_qualification.md#警告结果的外部探索性证据)
创建外部 ADS 探索用独立回执，保留失败和警告；它不生成 Touchstone、不满足
服务内 HB 放行、不认证网格收敛。必须分别核对外部文件映射、DC 和全部混频覆盖。

## 已审阅保存基线的接续

原 `set_parameters` 失败后，若其回执证明调用和参数刷新均已返回并保存，保存摘要、
工程身份、目标参数和当前工作流代次一致，且所属会话已审阅实际弹窗及不确定副作用，
原生只读回执完整匹配目标参数与必要实体、与该保存基线一致，再按会话状态处理：

- `needs_reconcile` 或 `close_failed`：按状态机完成针对原 job 的定向 reconcile；
  只读检查可在 reconcile 之前，仍须满足接口全部审阅条件。
- `ready`：若原失败回执的 `completion_evidence.reason` 为
  `verified_returned_saved`、`known_saved_geometry=true`、无监测失败或未决操作，
  则审阅并记录原 job、返回和保存证据、同一摘要、工作流代次以及只读回执。
  `ready` 不支持 reconcile，不要人为改变状态或修改原任务来制造 resolution。

满足对应分支及上述共同条件后，
可在既有授权范围内把该保存基线作为下一次 EM 的输入，不重写参数。保留原失败及
已有 resolution（若有）；`failed` 或 `resolved` 都不是 `succeeded`，实体存在和参数读回也不等于完整几何、依赖、
网格或求解通过。缺少返回/保存证据、现场未确定或基线变化则停止审阅。

提交 `solve` 前重新核对当前工程、保存摘要、用户要求、求解配置、实时空闲与弹窗；
依然使用绑定的工作流和其提交/执行时原生设置检查。不把原失败阶段加入 `depends_on`：
通用依赖只接受 `succeeded`，而已审阅的基线不是成功回执。只有上述完整证据支持的
基线接续可不声明该失败任务为依赖，不能借此绕过其他必要依赖或工作流门槛。

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

Before HB consumes new or changed EM data, apply the [HB coverage and stop gates](../cst-circuit/references/hb-and-postprocessing.md#hb-运行前的放行门槛). Read each actual passive block/file's valid data interval, including 0 Hz and the highest retained mixing frequency from actual tones/orders; a global frequency setting or a reference NPORT on another topology is insufficient. After topology/EM changes, pass bounded representative forward/reverse cases (DC operating point, actual RF incidence/matching and spectra) before the full parent sweep. The first initialization/numerical failure stops later groups and dependent templates without valid current-run inputs. These are caller orchestration requirements, not capabilities implied by the EM solver or HB configuration wrappers.

Confirm the target project, requested configuration, ports, boundaries and outputs before starting a costly solve. Record separately which settings were actually read back; when the user explicitly waives named noncritical readbacks for this run, proceed with the documented warning instead of imposing another check. Reuse the accepted geometry; do not silently rebuild or replace a user's project. Use `run_checked`/the service run contract, save before reading results, and report the exact run identity and status.

For multi-stage work, reload the [workflow checkpoint](../cst-sessions/references/workflow-checkpoint.md)
and check the requested stage before submission. Compare available evidence to the
latest requirements, not merely to the script's defaults; record explicitly waived
unavailable readbacks rather than silently inventing or blocking on them. A representative-point
check is an intermediate gate: retain the authorized full sweep and its expected
case set as a pending deliverable. Native warning review and numerical acceptance
remain separate from checklist consistency.

For parameter studies, prefer a suitable CST native sweep as described in
[cst-parameter-study](../cst-parameter-study/SKILL.md); configure once instead
of issuing per-point writes and solves. For specifically justified sequential
changes of existing geometry parameters, use session `set_parameters`
followed by session `solve`: the former invokes `app.update()`, which currently
calls SDK `model3d.full_history_rebuild()`; `rebuild_mode="parametric"` does
not mean a lightweight refresh. The latter calls `run_checked` without an
additional rebuild. Archive required results before updating. This is not
a configured native Parameter Sweep. Preserve complex per-case exports and verify
native IDs and parameter combinations after save/reopen; update success alone
does not guarantee all history survives. Full topology rebuild may delete results.

F-solver CPU parallelization uses `configure_fd_parallelization(settings)` through
the existing session `model_api`: boolean `enabled`, positive integer `threads`
and `cpu_devices` (sockets), with omitted fields preserved. Use explicit enabled=True
to turn it on; do not substitute transient `set_parallel_threads` or DS HB settings.
The receipt records configuration only; verify actual threads from the native run log.
This interface does not configure GPU acceleration or choose a different solver.

For F-solver linear comparisons use `configure_fd_linear_solver(settings)` with
`solver_type=Auto|Iterative|Direct` and optional explicit `limit_iterations/max_iterations`.
Do not use unrestricted SolverParameter keys or assume an iteration cap triggers Direct fallback.
Submit only `configure_fd_linear_solver/configure_fd_frequency/configure_fd_parallelization`
in one settings batch: the session automatically checks messages and saves without a full rebuild.
`configure_tetrahedral_mesh` can join this batch only with the newer worker
capability `mesh-settings-no-rebuild-v1`; it also avoids full Rebuild.
Mixed geometry batches still rebuild; keep them separate when retaining existing results matters.
The worker must advertise `solver-settings-no-rebuild-v1`; never restart a busy worker to upgrade.
No-rebuild receipts do not prove CST retained every result: archive required data and check native
IDs/readback in the authorized idle engineering session. Compare bounded cases before a full band.

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
