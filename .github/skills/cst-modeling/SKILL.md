---
name: cst-modeling
description: Plan, preview, create, or inspect general CST geometry through cst_solver. Use for entity, material, boolean, import/export, or port geometry work.
---

# CST modeling

Before constructing or materially changing geometry, derive a preview from the actual model parameters and show the intended geometry, ports, coordinate system, and key dimensions. Wait for the user's review before beginning construction. A text-only concept sketch does not verify geometry.

Keep units and coordinate conventions explicit. Prefer small, inspectable operations through `cst_solver`; preserve the user's existing project and unrelated work. After each dependent geometry stage, rebuild and record messages, entity counts, and output paths. Treat a clean rebuild as geometry evidence only; it does not establish solver success or device performance.

Read [the API guide](../../../docs/packages/cst_solver.md) when choosing `setup` methods and [Python usage](../../../docs/guides/python-usage.md) for examples.
