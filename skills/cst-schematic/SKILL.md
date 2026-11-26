---
name: cst-schematic
description: Inspect, create, wire or arrange a CST Design Studio schematic. Use for block properties, external ports, incremental connections, native sheet coordinates and linking an EM block to circuit pins.
---

# CST Design Studio 原理图编辑

先确定指定工程、需要检查或修改的对象，以及要交付的是接线、参数还是布局。操作真实工程时使用[所属会话](../cst-sessions/SKILL.md)和[许可宿主及后台启动器](../README.md#执行环境)，核对工程身份与原任务状态。原理图编辑使用受支持的 API。离线规格校验和拓扑预览可直接按[预览示例](../../docs/guides/circuit_cosimulation.md#不连接-cst-的使用方式)执行。

| 当前请求 | 操作与完成条件 |
|---|---|
| 查看已有元件、引脚或网络 | 在所属工程用 `circuit/build/inspect`，按实际名字报告所需对象、连接或位置。只读请求到此结束。 |
| 新建元件、端口，补线或改属性 | 按[增量接线与元件属性](../../docs/guides/circuit_cosimulation.md#增量接线与元件属性)使用当前引脚、网络、属性值与单位。新增对象和网络用 `circuit/build/configure` 分阶段提交。修改已有属性先核对当前接口能力。保存后对照请求读回实际成员和属性。 |
| 放置或移动符号，整理整张图 | 按[紧凑布局与整图可读性](../../docs/guides/circuit_cosimulation.md#紧凑布局与整图可读性)操作。新块与外部端口使用 `native_position`，移动已有对象使用 `set_position(..., coordinate_space="native")`。核对吸附后的坐标及前后连接；交付整图布局时，检查常用缩放下的符号、标签和连线。 |
| 把已有 EM 块接入原理图 | 按[EM 块与端口映射](../../docs/guides/circuit_cosimulation.md#em-块与端口映射)核对实际引脚、端口号、模式、参考端、极性及参数。同工程使用 `em_links` 和 `source="self"`。交付已保存的接线和核实的对应关系。 |

涉及三维几何或物理端口截面变化时，先按真实坐标预览并等待审阅。发生部分写入时保留回执，读取现场后只提交尚缺的修改。报告保存状态、实际读回项及仍缺的观察。后续要求配置或运行 SP、瞬态、HB 时进入[电路任务与场路联合](../cst-circuit/SKILL.md)；要求给 SP 添加自动导出时进入[结果模板配置](../cst-result-templates/SKILL.md)。
