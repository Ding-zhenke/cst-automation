---
name: cst-diagnostics
description: Diagnose CST installation, Python ABI, SDK import, solver stalls, dialogs, and structured task failures without guessing.
---

# CST diagnostics

Start with `python -m cst_solver doctor --json` and preserve the complete diagnostic report. Separate installation discovery, Python ABI match, import/DLL load, project readback, and solver execution; evidence for one stage does not prove a later stage.

For a stall, inspect the actual dialog title, body, buttons, process ID, and owning CST process before any response. Do not blindly dismiss prompts or rerun a write while the original SDK call may still be blocked. A timeout or a closed dialog is not success; state the observed status and next actionable step.

## Result incompatibility prompts: prefer API preparation

For `Results May Get Incompatible With Model`, read the [API handling guidance](../../docs/guides/cst_dialogs.md#结果失效弹窗的-api-预处理) before resorting to Computer Use.

- Before a model-changing call, determine the result-retention policy from existing user instructions. Preserve and verify any required results before cleanup; ask only if the needed choice is still unspecified.
- CST VBA `DeleteResults` is documented to delete all results of the actual project. Do not equate it with the dialog's **keep result cache** option or claim cache preservation without version-specific evidence. Confirm the target project and 3D/schematic execution context before invoking it through an available macro interface.
- Python `de.quiet_mode_enabled()` temporarily enables quiet mode and restores the prior state. It suppresses message boxes, but the official API excludes dialogs requiring user input; it does not guarantee suppression of this multi-option prompt or select a retention policy.
- Prefer preparing results through verified APIs before submitting the model change. If a call is already blocked, inspect the original task and dialog first; do not issue another SDK write to clear results or replay the change while it remains pending.
- These are documented CST API options, not a newly implemented repository endpoint or proof that the prompt has been eliminated on a real project. Retain dialog monitoring and verify the original call's return, messages, and resulting state.

See [environment setup](../../docs/guides/cst_environment.md), [dialog handling](../../docs/guides/cst_dialogs.md), and [troubleshooting](../../docs/guides/troubleshooting.md).
