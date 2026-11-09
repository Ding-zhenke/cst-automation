---
name: cst-diagnostics
description: Diagnose CST installation, Python ABI, SDK import, solver stalls, dialogs, and structured task failures without guessing.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# CST diagnostics

Start with `python -m cst_solver doctor --json` and preserve the complete diagnostic report. Separate installation discovery, Python ABI match, import/DLL load, project readback, and solver execution; evidence for one stage does not prove a later stage.

For a stall, inspect the actual dialog title, body, buttons, process ID, and owning CST process before any response. Do not blindly dismiss prompts or rerun a write while the original SDK call may still be blocked. A timeout or a closed dialog is not success; state the observed status and next actionable step.

## History errors: code and text first

Minimize Computer Use. Read the original session job/exception, CST messages and PID-scoped
`cst_solver.dialogs` snapshot first; the session worker already monitors dialogs independently
of the blocked SDK call. No routine screenshots or UI clicks are needed when this evidence is
complete. Read [the recovery procedure](../../docs/guides/cst_dialogs.md#历史错误优先代码诊断)
for bounded programmatic acknowledgement and the conditions requiring visual inspection.

For `Method or property not found`, trace the reported command to its source and check the
installed official VBA help and existing Python wrapper before correcting it. For example,
the CST 2026 DiscretePort help does not document `DiscretePort.Delete`; do not invent a
replacement method or treat this as proof of a missing port. A new empty project avoids
inherited history, but cannot make unsupported commands valid. Fix the source, retain the
failure evidence, and verify the corrected stage; never suppress the error or disable history
to report success. An unresolved call must return before any further SDK write or retry.

## Result incompatibility prompts: prefer API preparation

For `Results May Get Incompatible With Model`, read the [API handling guidance](../../docs/guides/cst_dialogs.md#结果失效弹窗的-api-预处理) before resorting to Computer Use.

- Before a model-changing call, determine the result-retention policy from existing user instructions. Preserve and verify any required results before cleanup; ask only if the needed choice is still unspecified.
- CST VBA `DeleteResults` is documented to delete all results of the actual project. Do not equate it with the dialog's **keep result cache** option or claim cache preservation without version-specific evidence. Confirm the target project and 3D/schematic execution context before invoking it through an available macro interface.
- Python `de.quiet_mode_enabled()` temporarily enables quiet mode and restores the prior state. It suppresses message boxes, but the official API excludes dialogs requiring user input; it does not guarantee suppression of this multi-option prompt or select a retention policy.
- Prefer preparing results through verified APIs before submitting the model change. If a call is already blocked, inspect the original task and dialog first; do not issue another SDK write to clear results or replay the change while it remains pending.
- These are documented CST API options, not a newly implemented repository endpoint or proof that the prompt has been eliminated on a real project. Retain dialog monitoring and verify the original call's return, messages, and resulting state.

See [environment setup](../../docs/guides/cst_environment.md), [dialog handling](../../docs/guides/cst_dialogs.md), and [troubleshooting](../../docs/guides/troubleshooting.md).

## 会话普通异常

对 session_operation_failed 先读 [受限异常诊断](../../docs/guides/session_exception_diagnostics.md)：
检查 error.details.diagnostics 的异常类型、OS filename/errno、最后执行 stage 及文件/函数/行号。
stage 不是成功检查点；PermissionError 或磁盘未变不授权重放未知写入，不猜 OS 原因。
旧 job 缺字段不回填；不为加载新诊断中断当前 CST 或 worker。

## 最终 clear 与首失败锁存

当 returned_saved 未能保持 ready，先读[收尾监测证据与加载代码身份](../../docs/guides/session_completion_monitor_evidence.md)：
主操作错误可与首个 monitor.failure 并存；最终 clear 不代表没有历史监测失败。检查
error.details.session_monitor、job.completion_evidence 与 worker_runtime，不拿磁盘 HEAD
当作活跃 worker 已加载版本。旧回执缺字段保持未知，不自动清围栏或重放写入。
