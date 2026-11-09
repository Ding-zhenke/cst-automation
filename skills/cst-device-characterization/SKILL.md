---
name: cst-device-characterization
description: Use when designing evaluation conditions or analyzing existing CST results for diode-based modulators, isolators, mixers, switches, or related nonlinear devices, including metric definitions and figure selection.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# 器件表征与报告

根据当前器件、任务和数据选择工况、指标及图形。以二极管器件为主要应用，通用数据方法也可用于其他驱动机制；不预设特定布局、端口数或固定图集。

1. 明确器件类型、被测输入/输出、控制端、源条件、参考面、阻抗、评价目标和当前交付范围。先读[器件指标](references/device-metrics.md)。
2. 核对同源工况、运行身份、单位和实际器件状态；多音、功率及波形处理先读[信号与证据](references/signals-and-evidence.md)。
3. 每项二极管器件性能评估都要给出实际 VAK(t) 曲线，与对应的 S 参数和性能指标图一并交付；标明实际工况、单位、极性及数据来源。需要解释调制工作状态时同时检查实际结端电流。数据缺失时列为缺项，不以源设定值替代结端电压，也不为补图擅自新增求解。
4. 图形样式及导出由 [cst-figures](../cst-figures/SKILL.md)统一，数据读取用 [cst-results](../cst-results/SKILL.md)。加载或偏置异常返回 [cst-diode-loading](../cst-diode-loading/SKILL.md)。
5. 给出指标定义、实际结果、适用工况、数值证据和未评估项。区别“数据已取得”“图已生成”和“目标已达标”。

这里指导研究设计与结果解释；执行配置/扫描/求解仍由 [cst-circuit](../cst-circuit/SKILL.md)及已有授权决定。
