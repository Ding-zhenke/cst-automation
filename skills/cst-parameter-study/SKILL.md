---
name: cst-parameter-study
description: Use when designing or configuring CST parameter sweeps, choosing linear or logarithmic ranges or discrete states, counting cases, or preparing an existing project for server scanning.
---

遵守[完整阅读规则](../README.md#完整阅读规则)。

# CST 参数研究

确认工程、参数/公式与单位、独立轴、基线、预期工况及输出。实际操作使用[所属会话](../cst-sessions/SKILL.md)。原生扫描能表达所需轴、任务依赖和输出时优先使用。配置前必读[采样、参数绑定与结果验收](references/axes-and-acceptance.md)，清点范围、端点、零值、组合数、极值约束、替换范围及结果存储。

| 任务 | 支持的路径 |
|---|---|
| 准备服务器扫描 | 在指定工程用专用会话 `configure_sweep` 配置，核对角点、恢复基线并保存工程、必要配套数据和配置 Python。按[工程生命周期](../cst-project-lifecycle/SKILL.md)交付。服务器准备授权仅含配置和交付。 |
| 配置原生 EM 序列 | 底层 `app.configure_sweep` 写原生配置；专用会话操作另执行常规模型重建、消息检查和保存。变更前保存所需结果。正常返回的重建可通过 INFO-only 队列；WARNING、ERROR、未知消息或重建未正常完成，按原回执审阅。绑定工程使用专用操作，按[绑定检查](../../docs/guides/workflow_enforcement.md)处理失效；受保护工程禁止通过 raw history 或 `model_api` 扫参配置方法旁路。 |
| 执行原生 EM 扫描 | 先确认独立的启动授权、具体原生任务及可用执行入口。当前发布会话没有注册扫描启动操作；底层有 `start_parameter_sweep()`，不等于会话已支持。普通 `solve` 调用单次 EM。需要在所属会话执行且缺少受支持入口时，说明缺口；保留工程绑定。按原生日志及实际结果判断执行状态。 |
| 每点依赖上个结果、原生任务无法表达要求，或用户明确指定逐点控制 | 已绑定会话按[参数修改示例](../../docs/guides/reusable_operations.md#参数修改示例)执行 `set_parameters`，审阅回执后提交已授权的 `solve`。当前发布的 `app.update()` 用 `RebuildOnParametricChange(False, False)` 刷新，假返回值报错；`run_checked` 不附加一次重建。核查实际 worker 版本。一次工程观察保留过两组参数和四条 S 叶，其他工程及保存重开仍须核验。 |
| 原生电路或场路研究 | 先核对 Design Studio 原生扫描及任务链。确有逐点证据、依赖或控制需求时，未绑定工程可按[电路研究入口](../cst-circuit/references/parameter-studies.md)使用底层 `app.circuit.run_parameter_study` 或允许的电路服务/MCP，它会保存和求解。当前原生会话的 `circuit(kind=study)` 在未绑定时要求规格，已绑定时拒绝非托管 study；不能据此声称存在同会话研究入口。 |
| 已完成扫描的逐点 Touchstone 或已有结果分析 | 按[结果技能](../cst-results/SKILL.md)在许可宿主用 `Result.export_touchstone_sweep()` 读取保存的工程，无需启动 DE 或求解。按实际正 Run ID、存储参数组合和完整复数矩阵导出，对照预期组合逐一核验。配置不保证每个预期工况已有结果；同一参数状态重算可覆盖 ID。单纯导出无需额外 HB 证据。 |
