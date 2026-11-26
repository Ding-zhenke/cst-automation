---
name: cst-single-diode-static-sp
description: Configure or verify one diode loaded onto a same-project CST EM block for static S-parameters, or export its loaded two-port schematic matrix as Touchstone for a specified parameter case.
---

# Single-diode static S-parameters and Touchstone

Start with the supplied artifact and requested output. For a circuit setup or run, identify the project, geometry, diode parameters, A/K mapping, SP task and external bias. Use the [owning session](../cst-sessions/SKILL.md) for live CST operations and the [licensed host and hidden launcher](../README.md#执行环境) from the first native call.

| Requested output | Read and finish at |
|---|---|
| Read an existing S2P file | Use [file-only result analysis](../cst-results/SKILL.md) on the supplied file. |
| Configure the diode-loaded static circuit | When building or changing the EM interface, read [junction geometry and terminals](references/static-sp.md#junction-geometry-and-terminals). For the schematic use [self-MWS wiring and SP setup](references/static-sp.md#self-mws-wiring-and-sp-setup). Save and verify the requested configuration. |
| Run static SP for a parameter case | Follow [case inputs and native execution](references/static-sp.md#case-inputs-and-native-execution). Check the worker supports the actual topology and bias before submitting. If that route is unavailable, report the missing capability. Reuse matching EM data for a diode-only change. Verify the native schematic run and loaded matrix. |
| Export a saved static SP run | Start at [export the loaded two-port](references/static-sp.md#export-the-loaded-two-port). Deliver the checked S2P and its case identity from the saved schematic curves. |
| Configure or validate automatic export | For a CST-hosted trigger read [native postprocessing](references/static-sp.md#cst-native-postprocessing-trigger). Configuration ends with saved binding and sequence readback. To demonstrate parameter-triggered export, follow [parameter-change verification](references/static-sp.md#parameter-change-verification) on the requested runs. |

For per-Run-ID files from a bare EM sweep use [saved EM results](../cst-results/SKILL.md). For a pumped isolator iteration continue through the [isolator workflow](../diode-isolator-design-workflow/SKILL.md).
