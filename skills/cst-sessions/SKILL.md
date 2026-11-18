---
name: cst-sessions
description: Manage independent persistent CST environments for separate conversations, including recovery and deduplication.
---

# 所属会话、工程与恢复

完整阅读本入口及当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

本机从首次原生调用起即使用有 CST 许可证的宿主。通过 Codex 命令工具导入 SDK、探测许可证、启动或恢复原生 worker（含 `resume`）、连接环境、打开工程、原生读结果或求解时，首次及后续命令均指定 `sandbox_permissions="require_escalated"`。Windows 非交互 Python 使用[后台启动器](../keysight-ads-simulation/scripts/invoke_hidden.ps1)，保留日志、退出码及 CST 诊断弹窗；只在用户明确要求时显示交互控制台。已有回执、导出 CSV 和 fake 测试可在沙箱读取或执行。

**已有工程的单次 EM** 可在已授权的宿主直接打开并调用 `app.run()`。先核对工程、已有任务状态及求解授权，再以本轮原生日志与结果判定完成。其余在线建模、配置、读取和求解默认复用对话所属会话。保护中的工程遵守其已绑定的工作流。

## 日常操作

1. 确定用户授权的工程、已保存基线及操作范围。缺少这项确认时先取得确认；同一基线和范围内的授权跨轮有效。每次接续核对现场、文件身份与原任务。未确认写入、基线实质改变或现场不明时重新审阅。
2. 首次建模前，以本仓库固定的 `work/sessions` 根目录、`work/conversations` 中新 UUID 引用建立会话。记录并告知恢复引用路径。新对话或分叉默认新绑定，有明确恢复要求时沿用旧绑定。后续通过同一 worker、DE 和明确的 `project_id` 操作；禁止无 PID 附加、按当前活动窗口选工程或用独立脚本接管已绑定工程。MCP 未启用时用同一虚拟环境的会话 CLI。见[首次绑定、状态查询与原任务接续](references/session-operations.md)。
3. 新器件默认从空工程和已审阅代码开始；续改或恢复时保留原工程及必需内容。同拓扑扫描、重试复用原身份。提交几何前按真实参数预览并等待审阅，用稳定的 stage_id/request_id 标识阶段与重试。初始参数、角点核验、正式路径与交付按[工程生命周期](references/project-lifecycle.md)。实机阶段按[工程验证](../cst-in-situ-validation/SKILL.md)记录实际证据。
4. 跨轮建模、EM→电路、优化或中断恢复先读[工程阶段清单](references/workflow-checkpoint.md)。保存当前要求、授权、工程和输入证据；用户纠正后先更新。提交依赖阶段前由调用方运行只读一致性检查。受管参数→EM→HB 链还须在空闲时绑定获准的规格，服务和 worker 自动执行[工作流检查](../../docs/guides/workflow_enforcement.md)。检查失败或旧 worker 缺少能力时保留现场与原回执，按安全接续程序办理。
5. 常规状态、停止范围、参数更新和已审阅基线按[已有操作](../../docs/guides/reusable_operations.md)。当前版本的 `set_parameters` 调用所属 `app.update()` 做参数刷新并检查消息，后续 `solve` 无需追加完整重建。改变历史或拓扑前保全所需结果，按原生运行身份、参数和曲线核验留存。独立记录配置、保存或重开、几何、实际求解与数值验收。

## 异常、交接与关闭

超时、断线或宿主启动失败时保留诊断，先查原 job、进程身份、弹窗和工程；不复制工程、换 ID 重交、强停或重放未知写入。worker 丢失后恢复原队列；软件更新本身不能证明正在运行的 worker 已加载新版。

| 触发条件 | 操作前必读 |
|---|---|
| 首次导入已复制或登记但失败 | [初始意图恢复](../../docs/guides/initial_project_intent_recovery.md)，在原 ID 上核验磁盘与空闲状态。 |
| 已返回且保存的电路失败、几何未验证、外部保存、`needs_reconcile` | [会话操作与失败审阅](references/session-operations.md#失败与基线审阅)。保留失败记录，只处理已审阅的 job。 |
| 停止 3D 后 DS 或后处理状态未明 | [停止与空闲的范围](../../docs/guides/solver_stop_scope.md)。确认对应序列空闲前禁止新写入或交接。 |
| 维护升级、保留 DE 的交接、静态准备后的旧 worker 已退出 | [worker 与工程交接](references/session-operations.md#worker-交接)。先确认队列、身份和现场，使用对应的完整协议。 |
| 3D History Error 后工程变化且有已验证原生归档 | 完整阅读[受保护归档恢复](../../docs/guides/model3d_archive_recovery.md)，保留同一事务、备份及原错误，再做定向现场审阅。 |
| 建模结束，需要关闭并清理过程工程 | [工程生命周期](references/project-lifecycle.md#临时检查标签有明确终点)。正式工程、配套数据和依赖核验后，通过 `close_project` 取得保存、关闭和退休回执，再删除本任务已确认的过程文件；保留 DE 和审计引用。 |
| 关闭整个 DE | 只在用户明确要求时使用所属会话 `close`。断线、一次回复结束、过程工程退休均保留 DE。 |

解释器、运行库身份与离线诊断见[环境与能力](references/runtime.md)；命令和返回字段见[会话指南](../../docs/guides/conversation_sessions.md)。私有工程和凭据留在当前工程环境，保持用户全局 MCP 配置。
