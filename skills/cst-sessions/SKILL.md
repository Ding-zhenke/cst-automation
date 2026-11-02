---
name: cst-sessions
description: Use when opening, resuming, or coordinating an explicit CST project across calls or conversations, including worker recovery and duplicate-request prevention.
---

# CST 对话会话

真实操作使用当前对话绑定的持久会话。首次操作先读[环境与能力](references/runtime.md)，分配或恢复时读[会话操作](references/session-operations.md)。源码讨论、离线分析和预览不启动 CST。

- 当前用户指令与已有授权优先；先确定工程、操作范围及恢复引用。
- 新对话使用独立引用、worker、DE 和工程目录。记录引用的绝对位置，后续复用；根目录服从目标工作区约定，不由插件安装位置决定。
- 配置、求解及在线读回经过所属会话，显式指定 project_id，不按活动窗口或任意 DE 连接。
- 超时先查原 request_id/job_id 回执；worker 丢失恢复原会话。不换 ID 重交未知写入，不自动重新导入或重建工程。
- needs_reconcile 时保留现场，经用户明确核对保存基线及空闲状态后再处理。恢复不提高几何或求解证据等级。
- DE 在回复和断线之间保留；仅按用户明确关闭请求关闭所属会话，不强杀其他任务。

几何改变用 [cst-modeling](../cst-modeling/SKILL.md)，电路任务用 [cst-circuit](../cst-circuit/SKILL.md)。
