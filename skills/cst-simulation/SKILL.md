---
name: cst-simulation
description: Configure and run CST electromagnetic simulations on an existing, reviewed project using cst_solver or tpc_service.
---

# CST simulation

For Design Studio schematics, EM links, or field-circuit tasks, use [cst-circuit](../cst-circuit/SKILL.md). Its current development scope prioritizes functions and skills; do not start dedicated validation solves unless required by the user's engineering task.

Confirm the target project, solver type, frequency range, ports, boundaries, mesh, and requested outputs before starting a costly solve. Reuse the accepted geometry; do not silently rebuild or replace a user's project. Use `run_checked`/the service run contract, save before reading results, and report the exact run identity and status.

Inspect real CST dialogs when an SDK call stalls. A timeout, open dialog, or closed dialog is not solver success. Keep offline/fake backend evidence separate from CST execution. Do not infer isolation, topology, or device performance from a successful solver return alone.

See [the CST API](../../docs/packages/cst_solver.md), [dialog procedure](../../docs/guides/cst_dialogs.md), and [troubleshooting](../../docs/guides/troubleshooting.md).
