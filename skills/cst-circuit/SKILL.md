---
name: cst-circuit
description: Use when configuring CST Design Studio schematics, nonlinear models, EM links, DC/HB/transient tasks, or coupled EM and circuit parameter studies.
---

# CST 电路与场路工作流

真实操作先用 [cst-sessions](../cst-sessions/SKILL.md)。使用 app.circuit 与 CircuitResult，先检查安装版本能力及签名。

| 需求 | 入口及边界 |
|---|---|
| 检查/预览 | inspect、validate_circuit_spec、preview_circuit；离线预览不打开 CST |
| 元件与连线 | apply/set_properties/list_pins，使用实际类型、引脚及单位 |
| 二极管/SPICE | configure_nonlinear_model，仅更新显式提供的字段 |
| 端口源/终端 | configure_task_ports；源设置不等于器件电压 |
| EM 连接 | link_em，显式 pin/port/mode/reference/polarity 与参数映射 |
| 瞬态/周期稳态 | configure_transient_task/configure_steady_state_task；配置不代表求解 |
| 任务运行 | run_checked；区分 network 和 transient_cosim |
| 参数研究 | run_parameter_study，会求解和保存，先读[参数研究](references/parameter-studies.md) |
| HB/原生扫描/回写 | 先读[HB 与结果刷新](references/hb-and-postprocessing.md) |

从原生读回元件、任务、单位、来源及依赖，区分全局参数与已被求值固化的属性。同一拓扑的 EM 与电路优先维护在同一工程；外部链接显式检查依赖闭包。

配置、保存、求解、读回和关闭重开分别记录。部分写入失败保留现场，不整批重试覆盖结果。源数据缺失时不为补图自行求解。

加载方法用 [cst-diode-loading](../cst-diode-loading/SKILL.md)，器件指标及选图用 [cst-device-characterization](../cst-device-characterization/SKILL.md)。
