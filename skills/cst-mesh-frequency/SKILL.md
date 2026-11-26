---
name: cst-mesh-frequency
description: Use when choosing or changing CST electromagnetic mesh density, local refinement, frequency sampling, or F-solver mesh adaptation points and convergence controls.
---

遵守[完整阅读规则](../README.md#完整阅读规则)。

# 网格与频率

Use [cst-sessions](../cst-sessions/SKILL.md) for actual project operations and
[cst-simulation](../cst-simulation/SKILL.md) for solving. For server preparation,
configure without local solving. Read actual geometry, units, materials, band, solver and
applicable controls before choosing settings; inherited automatic
settings alone are not a mesh plan.

If the user explicitly waives a named noncritical settings readback for the current
authorized EM run, record the submitted settings and mark the missing native
observation `warning / unverified`; do not hold that run for a getter, screenshot
or worker upgrade. This does not verify the settings, the eventual frequency
coverage, or mesh convergence, and does not waive project identity, unresolved
mutations or any other explicitly required check.

先按模型、材料或模式中的波长和局部特征估算网格成本。下述 Automatic/Single 频率表与 HF Tet 控制仅用于对应的频域求解器；时域 FIT 任务不加载这些分支，按六面体网格密度、局部尺寸及实际单元数核验设置，用网格加密与时域终止条件检查结果稳定性。

频域自适应：电尺寸大或求解成本高时，通常关闭 Automatic 行的 Adapt，初选两个或三个有物理代表性的 Single 点，再据截止、谐振或色散调整。电尺寸小且成本可承受时可采用有 pass 预算的 Automatic 自适应。

| 当前操作 | 必读引用 |
|---|---|
| 选择或调整网格密度、自适应点或求解预算 | [电尺寸、成本和代表频点](references/electrical-size.md) |
| 改模型频带、采样行、显示点数、局部网格、pass/Delta-S，或核验设置读回 | [频率表和自适应](references/frequency-and-adaptation.md) |
| 提交类型化网格或 F 求解器频率、线性、并行设置 | [设置历史及实际 worker 能力](references/hf-tet-controls.md#设置历史)，再读对应控制段落 |
| 改 HF Tet 曲率、精度、离散阶次、边沿或密度控制 | [HF Tet 专项控制](references/hf-tet-controls.md)中对应章节 |
| 出现低质量单元或需要解码已保存的 mesher 输入 | [警告快照与输入核验](references/mesh-warnings.md) |

| Control | Purpose / API |
|---|---|
| Model band | `set_frequency_range`; preserve parameter references |
| Actual broadband frequency sampling | `configure_fd_frequency` → `sampling_intervals` |
| Mesh-adaptation frequencies | same API → `adaptation_frequencies` (Single, Adapt=True), or explicit interval `adaptation` boolean |
| Display/interpolated result resolution | `output_samples`, strict integer >=3; a dense curve is not that many independent solves |
| Shared sweep/result axis mode | `output_spacing`; CST applies it to adaptive sampling and output axes |
| Global tetrahedral density, material refinement | `configure_tetrahedral_mesh` |
| Local tetrahedral solid size | same API → `local_solids` |
| Pass/Delta-S refinement convergence | same API → `adaptation` |
| Linear-equation residual | `configure_fem_solver(accuracy=...)`; independent of mesh/Delta-S convergence |
| HF tetrahedral polynomial order | `configure_fd_linear_solver` → `tet_order` and `mixed_order`; changes discretization, not residual/Delta-S acceptance |
