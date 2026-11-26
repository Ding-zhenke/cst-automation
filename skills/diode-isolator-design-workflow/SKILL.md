---
name: diode-isolator-design-workflow
description: Coordinate diode isolator iterations across CST EM, same-project zero-bias circuit S-parameters and pumped ADS HB. Use for stage handoffs, candidate reuse and resumption.
---

# Diode isolator design workflow

Read this entire entry and the sections required by the chosen stage. Follow the [complete reading rule](../README.md#完整阅读规则) after truncation or context loss.
Use the current project configuration and original conversation session; never infer
device dimensions, model parameters, port mappings or targets from another project.

## Single-diode microstrip and static Touchstone export

For a single loaded diode and its static S2P deliverable, use [single-diode static SP](../cst-single-diode-static-sp/SKILL.md).

## Isolator workflow with pumped HB

The sequence is parameters → CST EM → CST Design Studio S-parameters with diodes,
zero external DC and pump → ADS HB with separately specified bias and pump → joint
analysis → next candidate. The SP task's measurement excitation remains enabled.
Do not substitute 3D EM S-parameters, offline linear predictions or a pump-off
biased result for native zero-bias circuit SP.

For unchanged topology reuse the same CST project, path and window across candidates;
archive per-candidate inputs, matrices, raw outputs, logs and plots outside the
project without routinely copying the entire project. Verify actual native history
association and retention; a positive run ID alone is not persistence evidence.

Run noninteractive helpers, test processes and background solvers without opening
a console window. On Windows use `cst_automation.process.hidden_console_flags`
with existing process flags; keep pipes, logs, process groups and lifecycle rules.
An already detached worker must not combine `DETACHED_PROCESS` and
`CREATE_NO_WINDOW`. Interactive user tools and CST windows retain their own UI.

Use [sessions](../cst-sessions/SKILL.md), [circuit](../cst-circuit/SKILL.md),
[results](../cst-results/SKILL.md), and [ADS](../keysight-ads-simulation/SKILL.md)
for their actual stages and existing enforced gates. Bind results to the exact
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

- When several ADS circuits or scans share one SNP, read [shared network input](references/engineering-handoffs.md#shared-snp-input-for-ads-circuits-and-scans) before changing source configuration or running a generated netlist.
- For static SP preparation, reviewed recovery or measurement ports, read [static SP routes](references/engineering-handoffs.md#static-sp-routes) and the [integration contract](../../docs/guides/diode_workflow_integration.md). Verify the actual terminations and EM identity. Keep exploratory and formal acceptance separate.
- For a requested diode performance evaluation, deliver actual VAK(t) with the matching metrics and source data under [device characterization](../cst-device-characterization/SKILL.md).

For resumption inspect original CST job and session first; unknown or active jobs
must not be resubmitted. `cst_automation.workflow_resume.missing_cases` is only an
offline candidate list: verify actual artifact bytes, case identity, solver status
and validity before reusing or submitting any ADS point. This helper is not a
runner, state store, qualification gate or evidence of complete numerical results.
Project adapters may use the separate `cst_automation.design_state.DesignState`
SQLite journal to reserve requests and retain immutable attempts. Read the
[integration contract](../../docs/guides/diode_workflow_integration.md); its
caller assertions do not replace native receipts, archive checks or solver gates.

Report raw complex data, units and input identities separately from numerical
quality and performance conclusions. Preserve failures and independent mesh,
residual, sampling, DC-fit and HB-truncation evidence. Bounds on diagnosis and
resource use come from the project; do not silently relax acceptance thresholds.

## Shared SNP input for ADS circuits and scans

When several ADS circuits share one EM network, follow the [shared SNP source, netlist and archive checks](references/engineering-handoffs.md#shared-snp-input-for-ads-circuits-and-scans).
