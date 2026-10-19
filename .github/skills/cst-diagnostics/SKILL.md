---
name: cst-diagnostics
description: Diagnose CST installation, Python ABI, SDK import, solver stalls, dialogs, and structured task failures without guessing.
---

# CST diagnostics

Start with `python -m cst_solver doctor --json` and preserve the complete diagnostic report. Separate installation discovery, Python ABI match, import/DLL load, project readback, and solver execution; evidence for one stage does not prove a later stage.

For a stall, inspect the actual dialog title, body, buttons, process ID, and owning CST process before any response. Do not blindly dismiss prompts or rerun a write while the original SDK call may still be blocked. A timeout or a closed dialog is not success; state the observed status and next actionable step.

See [environment setup](../../../docs/guides/cst_environment.md), [dialog handling](../../../docs/guides/cst_dialogs.md), and [troubleshooting](../../../docs/guides/troubleshooting.md).
