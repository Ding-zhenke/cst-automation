---
name: cst-device-characterization
description: Use when designing evaluation conditions or analyzing existing CST results for diode-based modulators, isolators, mixers, switches, or related nonlinear devices, including metric definitions and figure selection.
---

完整阅读本入口及当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

# 器件表征与报告

根据当前器件、任务和数据选择工况、指标及图形。以二极管器件为主要应用，通用数据方法也可用于其他驱动机制；不预设特定布局、端口数或固定图集。

1. 明确器件类型、被测输入/输出、控制端、源条件、参考面、阻抗、评价目标和当前交付范围。先读[器件指标](references/device-metrics.md)。
2. 核对同源工况、运行身份、单位和实际器件状态；多音、功率及波形处理先读[信号与证据](references/signals-and-evidence.md)。
3. 评估二极管时按[逐管电压交付](references/signals-and-evidence.md#逐管电压交付)核对各管实际 VAK(t) 与对应指标、图及来源。涉及 HB 与独立瞬态的比较另读[对照条件](references/signals-and-evidence.md#hb-与瞬态结果对照)。
4. 图形样式及导出由 [cst-figures](../cst-figures/SKILL.md)统一，数据读取用 [cst-results](../cst-results/SKILL.md)。加载或偏置异常返回 [cst-diode-loading](../cst-diode-loading/SKILL.md)。
5. 给出指标定义、实际结果、适用工况、数值证据和未评估项。区别“数据已取得”“图已生成”和“目标已达标”。

这里指导研究设计与结果解释；执行配置/扫描/求解仍由 [cst-circuit](../cst-circuit/SKILL.md)及已有授权决定。
