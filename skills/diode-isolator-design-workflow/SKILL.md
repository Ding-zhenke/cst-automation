---
name: diode-isolator-design-workflow
description: Coordinate diode isolator iterations across CST EM, same-project zero-bias circuit S-parameters and pumped ADS HB. Use for stage handoffs, candidate reuse and resumption.
---

# Diode isolator design workflow

Identify the current candidate and the last completed stage in its [owning session](../cst-sessions/SKILL.md). Use that project's geometry, materials, diode model, port map, operating conditions and targets. Follow the [complete reading rule](../README.md#完整阅读规则) for the authorized stage.

## Single-diode microstrip and static Touchstone export

For a single loaded diode and its static S2P deliverable, use [single-diode static SP](../cst-single-diode-static-sp/SKILL.md).

## Isolator workflow with pumped HB

| Stage | Evidence to carry forward |
|---|---|
| Current candidate | Record its identifier, exact parameters and topology in the original project. For unchanged topology, retain the CST project, path and window across candidates. |
| CST EM | Bind the native run and its [complex S-matrix](../cst-results/SKILL.md) to that candidate. Check the port map, frequency coverage and applicable EM acceptance criteria before handing off the matrix. |
| Zero-bias CST circuit SP | Run the [same-project Design Studio SP](../cst-circuit/SKILL.md) with the diodes connected, zero external DC and pump, and measurement excitation enabled. Carry forward the native task, run identity and loaded complex S-parameters. |
| Pumped ADS HB | Use the matching EM network and the specified RF, bias and pump in [ADS HB](../keysight-ads-simulation/SKILL.md). Keep the dataset and solver log with the actual source settings, directions and frequency grid. |
| Joint analysis and next candidate | Compare the matching circuit SP and HB data against the project criteria. Record the observed limitation, which candidate inputs will change, and the next affected stage. |

Archive per-candidate inputs, matrices, raw outputs, logs and plots outside the shared project. Verify the saved native run–parameter association and result retention before reusing an earlier case. Bind results to the exact
geometry, materials, ports, model, source conditions and EM input. A changed ADS
bias or pump alone does not invalidate matching EM or zero-bias SP. Keep zero-bias
SP and HB source settings distinct. Never claim a configured task was executed.

## 每组最终几何的三组结果图

交付隔离器仿真或优化结果时，按以下顺序生成并展示每组最终几何的三组图。用户点名只看局部结果时，按所选范围交付。

1. **静态 SP**。使用指定直流偏置、关闭泵浦的小信号 SP。传输面板叠画 S21/S12，反射面板叠画 S11/S22。注明实际偏置及重合曲线。流程中的零偏 SP 仅在指定偏置为零时用作这组对照。
2. **带泵 HB 载波**。在同一偏置和泵浦条件下分别激励两个 RF 端口，提取原 RF 载波。传输面板叠画 S21/S12，反射面板叠画 S11/S22。若叠加静态对照，同一 S 参数用同色，HB 用实线，静态用虚线。
3. **隔离度与插损**。同图画带泵 ISO、带泵 IL、同几何同偏置的静态 IL。先按当前项目确定通行方向，以 dB 传输量计算 IL = −T通、ISO = T通 − T阻，保留 ISO 符号；静态 IL 取同一通行方向。默认标出 20 dB 隔离线、10 dB 插损线及实际优化频段，项目另定指标时采用其限值。

三组图用 RF 输入频率（GHz）和幅值（dB），展示完整已有扫频。对照数据核对几何、端口、参考面和 RF 采样点。图注注明偏置、泵浦频率与波形、RF 激励功率和通行方向。收尾逐组打开导出图，核对面板和曲线，按 1–3 列出对应文件。缺数据时先交付已有曲线，并列明缺少的方向、频点或工况。

## Which handoff to use

- For static SP preparation, reviewed recovery or measurement ports, read [static SP routes](references/engineering-handoffs.md#static-sp-routes) and the [integration contract](../../docs/guides/diode_workflow_integration.md). Verify the actual terminations and EM identity. Keep exploratory and formal acceptance separate.
- For a requested diode performance evaluation, deliver actual VAK(t) with the matching metrics and source data under [device characterization](../cst-device-characterization/SKILL.md).
- When resuming a scan, inspect the original session and job first. Reuse a point only after checking the actual case, solver status and saved data. Leave active or unresolved submissions with their original job. For a scan driver, use the [resumption and journal checks](references/engineering-handoffs.md#scan-resumption-and-project-journals).
- To implement a new noninteractive Windows launcher, read the [background process settings](references/engineering-handoffs.md#windows-background-processes). For engineering work, use the standard [hidden launcher](../README.md#执行环境).

Report raw complex data, units and input identities alongside the relevant mesh, residual, frequency sampling, DC-fit and HB-truncation evidence. Preserve failures and the project's resource limits and acceptance thresholds.

## Shared SNP input for ADS circuits and scans

When several ADS circuits share one EM network, follow the [shared SNP source, netlist and archive checks](references/engineering-handoffs.md#shared-snp-input-for-ads-circuits-and-scans).
