---
name: cst-sessions
description: Bind CST work to its owning conversation, check session or job status, recover an interrupted operation, or hand off its worker.
---

# CST 所属会话与恢复

确定已授权的工程、已保存基线和本次操作范围。同一范围跨轮沿用；基线实质变化、未知写入或现场不明时，先核对原任务与工程。已有工程的单次 EM 可按[EM 仿真](../cst-simulation/SKILL.md)在已授权的宿主直接打开运行。其余在线工程操作默认使用所属会话。

首次 SDK 导入、许可证探测、原生 worker 启动或恢复（含 `resume`），以及后续原生调用，均在有许可证的宿主执行。Codex 命令指定 `sandbox_permissions="require_escalated"`，Windows 非交互 Python 使用[后台启动器](../keysight-ads-simulation/scripts/invoke_hidden.ps1)并保留日志、退出码和诊断弹窗。离线读取已有回执按[执行环境](../README.md#执行环境)操作。

## 日常操作

- **首次绑定。** 在本仓库固定的 `work/sessions` 根目录登记会话，以 `work/conversations` 中的新 UUID 引用绑定并告知用户恢复引用路径。新对话或分叉默认新绑定，明确接续时沿用旧引用。命令见[首次绑定](references/session-operations.md#首次绑定)。
- **日常提交或读状态。** 复用对话的引用、worker、DE 和明确的 `project_id`，使用稳定的 `request_id`，分阶段写入时同时使用稳定的 `stage_id`。只查状态时，在所属引用上用 `status` 和必要的 `job --job-id JOB_ID` 读取并报告。仅有请求 ID 时按[状态查询与提交](references/session-operations.md#状态查询与提交)定位原任务。MCP 缺席时使用同一虚拟环境的 CLI。禁止无 PID 附加、按当前活动窗口选工程或用独立脚本接管已绑定工程。
- **创建、导入或续用工程。** 新器件从空工程和已审阅代码开始，几何写入前按真实参数预览并等候审阅。续改、同拓扑扫描与重试复用原工程。按操作读[新工程与初始参数](references/project-lifecycle.md#新器件从空工程开始)、[正式路径](references/project-lifecycle.md#操作前确定一个目标)或[原位角点核验](references/project-lifecycle.md#一次配置原位核验)。参数刷新、既有基线和停止范围见[已有操作](../../docs/guides/reusable_operations.md)。
- **跨轮建模、EM→电路或优化。** 进入依赖阶段前按[工程阶段清单](references/workflow-checkpoint.md)核对当前要求、输入和证据。用户纠正要求时先更新清单。受管参数→EM→HB 链在空闲时绑定获准规格，并执行[工作流检查](../../docs/guides/workflow_enforcement.md)。

## 异常、交接与关闭

- 超时、断线、未知任务或 worker 失联时，先查原 job、进程、弹窗及工程，按[接续原任务](references/session-operations.md#接续原任务)恢复原队列。有恢复或维护需求时才读[相应异常与交接分支](references/session-operations.md#按现场选择处理程序)。
- 进入正式交付或建模结束时，按[工程交付与过程工程清理](../cst-project-lifecycle/SKILL.md)核对依赖，并主动收尾本任务的过程工程。单个标签用 `close_project`，整个 DE 的 `close` 只在用户明确要求时提交，使用稳定的 request-id。
- 核对实际加载的解释器、模块和 worker 能力时查[环境与能力](references/runtime.md)。版本更新后以当前 worker 的能力读回为准。私有凭据和工程资料留在当前工程环境。
