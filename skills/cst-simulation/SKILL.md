---
name: cst-simulation
description: Configure and run CST electromagnetic simulations on an existing, reviewed project using cst_solver or tpc_service.
---

遵守[完整阅读规则](../README.md#完整阅读规则)。

# CST 电磁仿真

本机真实 CST 操作从首次原生调用起就在可验证许可证的宿主环境执行。
用 Codex 命令工具启动时，首条会导入 CST SDK、打开工程或启动原生 worker 的命令
即指定 `sandbox_permissions="require_escalated"`。已有工程的单次
`setup(project_path)`、`app.run()` 同样适用。启动求解仍需当前任务的授权。
Windows 下首个非交互 Python 进程用[后台启动脚本](../keysight-ads-simulation/scripts/invoke_hidden.ps1)运行，保留原生求解日志和 CST 弹窗。

## 已有工程的单次 EM

核对指定工程、已审阅的几何和设置、已保存基线、先前任务状态及本次求解授权。独立且未受已有工作流保护的工程，可直接调用 `app = setup(project_path)`、`app.run()`，也可用未绑定工作流的所属会话提交 `solve`。独立运行无需新建会话或绑定工作流。保留已接受的几何，保存结果后按实际原生日志和数据报告完成情况与收敛。器件隔离度等指标以该工况实测曲线计算。阻塞或弹窗按[诊断](../cst-diagnostics/SKILL.md)核实。

已有绑定或在途任务按[所属会话](../cst-sessions/SKILL.md)继续。参数 → EM → HB 执行[绑定规格](../../docs/guides/workflow_enforcement.md)的提交与执行检查。需要额外保护的独立 EM 可选 schema v2 `em_only`。当前任务明确豁免的非关键独立读回，只在本轮记录具体字段、已下发值及 `warning / 未独立读回`，可继续已授权求解。既有绑定断言仍须通过；工程身份、参数、保存状态和未知写入须核清。

## 按操作读取

| 触发条件 | 必读内容与边界 |
|---|---|
| 选择频率表、网格与自适应点 | [网格与频率](../cst-mesh-frequency/SKILL.md)。核算电尺寸，区分实际采样、插值和网格迭代；保留目标残差和 Delta-S 判据。 |
| 更改 F 求解器并行、线性设置、瞬态时间设置，或残差未达到目标 | [求解器设置与有界回退](references/solver-settings.md)，按相关段执行。配置回执与实际线程、时间步、残差分别核验。 |
| 配置或运行参数扫描 | [参数研究](../cst-parameter-study/SKILL.md)。专用 `configure_sweep` 只配置。服务器准备在原工程核对角点、恢复基线并保存；单次 `solve` 不能启动参数扫描。 |
| 受保护参数更新失败但已返回并保存 | [已审阅保存基线的接续](references/saved-baseline.md)。按原回执和状态核验再提交。 |
| 多阶段工作或下游场路/HB 使用新 EM | [EM 交接与验证](references/em-handoff.md)和[场路技能](../cst-circuit/SKILL.md)。配置、数值验收与工程交付各自记录。专用验证求解以当前授权为准。 |
