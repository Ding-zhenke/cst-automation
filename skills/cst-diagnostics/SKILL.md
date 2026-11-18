---
name: cst-diagnostics
description: Diagnose CST installation, Python ABI, SDK import, solver stalls, dialogs, and structured task failures without guessing.
---

读完本入口和当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

# CST diagnostics

For installation discovery, `python -m cst_solver doctor --json` can run in the
sandbox. For an SDK import check, run `python -m cst_solver doctor --json --probe`
on the approved host on the first attempt. In Codex command tools, set
`sandbox_permissions="require_escalated"` on that call and on commands that
check the native license. Preserve the complete report. Assess installation
discovery, Python ABI compatibility, SDK/DLL loading, license availability,
project readback and solver execution separately.
Use the [hidden launcher](../keysight-ads-simulation/scripts/invoke_hidden.ps1) for either
noninteractive Python command on Windows; keep CST diagnostic dialogs visible.

For a stall or timeout, inspect the original job/exception, messages, logs and PID-scoped window title, complete body, buttons and owning process. Raw View can recover missing text; unresolved text remains unknown. Keep the original failure. A dismissed dialog or a ready session cannot certify the solver or authorize replay of an unresolved write. Prefer structured evidence before screenshots.

| Observed condition | Required procedure before acting |
|---|---|
| Run or stop status only | Use [read-only status operations](../../docs/guides/reusable_operations.md). Separate status inspection from answering a prompt. |
| Stop scope uncertain or Qt abort prompt | Read [3D/DS stop scope](../../docs/guides/solver_stop_scope.md) and [explicit Qt confirmation](../../docs/guides/cst_dialogs.md#qt-停止确认的显式-yes). Confirm only an exactly matched prompt under existing stop authorization; pending or unknown DS state blocks new writes and handoff. |
| History error or unavailable VBA method | Follow [history error diagnosis](../../docs/guides/cst_dialogs.md#历史错误优先代码诊断). Use installed official help and the actual wrapper to repair the source. Preserve the error and wait for the original call to return before writing. |
| Result invalidation, cache selection or repeated INFO | Read [result-retention decisions](../../docs/guides/cst_dialogs.md#结果失效弹窗的-api-预处理). Preserve and verify required data first. For the known authorized cache choice, inspect, select, independently inspect, then confirm. Freeze and read the saved copy noninteractively before a rerun. Repeated messages remain evidence; quiet mode, window disappearance or a selection receipt cannot verify cache integrity. |
| Ordinary session exception | Read [bounded exception diagnostics](../../docs/guides/session_exception_diagnostics.md). Record the failing stage, OS error and bounded stack. Prior receipts without these fields stay unknown. |
| Returned/saved action with a latched monitoring failure | Read [completion evidence](../../docs/guides/session_completion_monitor_evidence.md). Record the original error, first monitor failure, final snapshot and loaded worker identity. A clear final snapshot does not release a prior fence. |

For setup and further diagnosis, use [environment setup](../../docs/guides/cst_environment.md), [dialog inspection](../../docs/guides/cst_dialogs.md) or [troubleshooting](../../docs/guides/troubleshooting.md). Keep the active worker intact when its diagnostics are older than the source.
