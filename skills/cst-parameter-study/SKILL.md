---
name: cst-parameter-study
description: Use when designing or configuring CST parameter sweeps, choosing linear or logarithmic ranges or discrete states, counting cases, or preparing an existing project for server scanning.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# Parameter-study selection

Actual operations use [cst-sessions](../cst-sessions/SKILL.md). Check the target
project, independent axes, parameter formulas/units, baseline, outputs and run
authorization. Reuse the accepted project when topology is unchanged. A request
to configure a server scan does not authorize starting the scan locally.

Default to CST's native parameter sweep when it can express the requested axes,
task dependencies and required outputs. Configure it once and run the native
task under the existing authorization; avoid repeated Python parameter writes,
updates and solves for every point, which add communication and write latency.
Check the actual project, native task type, parameter binding and result storage
first; configuration alone does not prove a sweep was executed or preserved.

Choose the appropriate mechanism:

- Native EM sweep configuration: `setup.configure_sweep` or session operation
  `configure_sweep`; editable in CST and no solve starts.
- Serial EM points in one existing project only when native sweep cannot meet a
  specific requirement (such as dependent per-point decisions, unsupported task
  behavior or explicitly requested per-point control): session `set_parameters` refreshes
  with `app.update()` and checks messages; session `solve` then runs without a
  second full rebuild. This is distinct from configuring a native sweep. A live
  case retained two parameter states and all four S leaves using this SDK update
  path; saving/reopening and general retention are not yet certified.
- Coupled EM/circuit or pure-circuit study: first check the applicable native
  Design Studio sweep and task chain. Use [cst-circuit](../cst-circuit/SKILL.md)
  `run_parameter_study` when native operation cannot meet explicit per-case evidence,
  dependency or control requirements. It saves and solves and is not a native sweep.
- Existing case analysis: [cst-results](../cst-results/SKILL.md), retaining actual
  run identity, units and complex data. Do not treat the current run as all cases.

## Choose axes rather than defaulting to fixed points

| Physical sampling need | Native specification |
|---|---|
| Geometry, bias or narrow-range search at equal differences | `{"mode":"linear", "start":lo, "stop":hi, "samples":count}` |
| Positive conductivity/lifetime/loss across orders of magnitude | same descriptor with `mode="logarithmic"` |
| Exact reference states, irregular values, zero, switches | explicit finite number list |

These descriptors are values in a parameter-name mapping. They retain native
linear/logarithmic mode via `AddParameter_Samples`, rather than expanding every
range into arbitrary points. `samples` counts both endpoints, not intervals;
logarithmic bounds must be positive. Zero plus a logarithmic range requires a
separate zero-state sequence or an intentionally discrete list including zero.
Do not silently drop zero or change its physical meaning.

`configure_sweep(sequence_name,parameters,replace_all=False)` validates the whole
mapping before a single history entry. `configure_discrete_sweep` is the legacy
point-list-only interface. Low-level `add_sweep_parameter_samples` exposes a
boolean logarithmic flag; prefer the complete mapping for reviewable studies.
Avoid old `configure_parameter_sweep`: it mixes configuration and execution and
uses legacy unsupported sequence commands. Run only through the explicit,
reviewed execution path after the authorized scope is known.

Axes in one sequence form a Cartesian product; separate sequences are independent
experiments. Count the product per sequence and sum across sequences. This API
does not promise zipped/simultaneous axes. Review combinations, baseline/reference
states, geometry validity at extrema and intended outputs before submission.
Current software bounds are 100 axes, 10000 points per axis and 1000000 cases per
sequence; these are input limits, not an affordable compute budget. Use coarse
then focused sampling when warranted; do not launch that extra work implicitly.

Check that the swept parameter actually drives the model: material conductivity
must reference the conductivity parameter, and geometry dimensions must retain
the intended formulas. A parameter table entry alone does not establish binding.

Choose mesh/frequency settings using
[cst-mesh-frequency](../cst-mesh-frequency/SKILL.md). Separate frequency solves,
mesh adaptation and parameter cases; estimate electrical size/cost first. Do not
assume a mesh remains adequate after a geometry or material-state change.

Check the current parameter names and dependencies, explicit sequence replacement,
native ranges/counts/log flags and resulting total cases. `replace_all=True`
deletes existing sequences; use only when replacement is intended. Corner checks
reuse the project and restore baseline values. Retain a single final project,
necessary paired data and modeling/configuration Python with clear server
instructions. Unknown native readback stays unverified; offline tests, native
configuration, completed runs and numerical convergence are separate evidence.
When acceptance requires retained native history, check two different geometric parameter combinations
in the same project: all four complex S leaves, each state's positive 3D Run ID
and actual stored parameter combination, then save, close and reopen and repeat
the reads. Keep exported complex data and logs; same-state reruns can overwrite an ID.
