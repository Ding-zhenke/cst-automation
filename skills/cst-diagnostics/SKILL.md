---
name: cst-diagnostics
description: Diagnose CST installation and SDK failures, or determine what happened to an existing job from its logs, process identity, dialogs and receipts.
---

# CST diagnostics

Follow the [complete reading rule](../README.md#完整阅读规则) for the observed symptom.

For a stall, timeout or failure, identify the original job, owning session, project and CST PID. Read the job state, original exception, messages and logs. If the native outcome or a write is still unknown, retain the original failure and leave the operation pending review. To continue that job or recover its project, use the [owning session](../cst-sessions/SKILL.md).

For a possible dialog, read the [PID-scoped dialog snapshot](../../docs/guides/cst_dialogs.md). Check its owner, title, complete body and buttons. Use Raw View for missing text and Computer Use for unresolved content or a necessary action unavailable through the API. After a dialog action, check the original call and its outcome. A recognized Quiet/Scripting mode notice permits API work to continue in scripting mode. Switch to interactive mode only for a concrete UI task after the owning operation is idle.

| Observed symptom or request | Read the corresponding procedure |
|---|---|
| Check whether a job is still running or has stopped | [Read-only status of the original job](../../docs/guides/reusable_operations.md#原任务联合只读核查). |
| Stop scope is unclear, or a Qt abort confirmation is open | [3D/DS stop scope](../../docs/guides/solver_stop_scope.md) and, for an already authorized stop, [exact Qt confirmation](../../docs/guides/cst_dialogs.md#qt-停止确认的显式-yes). |
| History Error or missing VBA method | [Failed command, installed official help and original call](../../docs/guides/cst_dialogs.md#历史错误优先代码诊断). |
| Result invalidation, cache choice or repeated INFO | [Retention and message evidence](../../docs/guides/cst_dialogs.md#结果失效弹窗的-api-预处理). For an authorized cache choice, follow [selection, independent readback, confirmation and frozen-data checks](../../docs/guides/reusable_operations.md#有限缓存选项流程). |
| Ordinary session exception | [Failing stage, OS error and bounded stack](../../docs/guides/session_exception_diagnostics.md). |
| Monitoring failed even though the call later returned or saved | [Original error, first monitor failure, final snapshot and loaded worker](../../docs/guides/session_completion_monitor_evidence.md). Preserve the first failure when the final snapshot is clear. |

## Installation and SDK checks

For installation discovery, `python -m cst_solver doctor --json` can run in the sandbox. For an SDK import check, run `python -m cst_solver doctor --json --probe` on the licensed host on the first attempt with `sandbox_permissions="require_escalated"`. Use the same host permission for a license check. Launch unattended Windows Python through the [hidden launcher](../keysight-ads-simulation/scripts/invoke_hidden.ps1) and preserve the full report.

Report the observed stage of installation discovery, interpreter ABI, SDK/DLL loading, license access, project readback or solver execution. For that stage, use the [environment guide](../../docs/guides/cst_environment.md) or [troubleshooting](../../docs/guides/troubleshooting.md). Keep the active worker intact when its diagnostics predate the source.
