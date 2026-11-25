---
name: cst-result-templates
description: Register a built-in CST Result Template in a 3D project or a Design Studio Post task. Use when the project needs an automatic post-processing step such as Touchstone Export.
---

# Configure a CST result template

Identify the saved, idle project, installed template category and display name, destination, and requested settings. Use the [owning session](../cst-sessions/SKILL.md). From the first native call, use the licensed host with `sandbox_permissions="require_escalated"` and the [hidden launcher](../keysight-ads-simulation/scripts/invoke_hidden.ps1) for unattended Windows Python.

- **3D project.** Register the step in the project's Result Templates list. For automatic Touchstone export, use the [3D settings and example](references/touchstone-export.md#3d-project).
- **Design Studio.** Follow [SP binding and sequence order](references/touchstone-export.md#design-studio). For automatic export after each SP update, also read back the source SP binding and verify that its Post task follows it in the same native sequence.
- **Other installed templates.** Use the [registration API contract](../../docs/PUBLIC_API.md#add-an-installed-cst-result-template) for native setting keys, tree references and dynamic result types.

Use `add_builtin_result_template` on a worker advertising `builtin-result-template-v1`. Registration saves, closes and reopens the owned project. Reacquire cached project handles. For configuration, finish when the receipt confirms `registration_persistence_verified` and `reopen_verified`. Report `template_execution_verified` as returned. When execution is also requested, check the newly generated result. For Touchstone, verify the source, grid, port order, format and impedance.

For files from an already saved EM sweep, use [saved-result export](../cst-results/SKILL.md).
