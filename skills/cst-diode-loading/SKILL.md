---
name: cst-diode-loading
description: Use when loading diodes into CST structures or circuits, selecting lumped or physical representations, checking A/K and bias paths, package parasitics, mesh, or nonlinear numerical validity.
---

# 二极管加载方法

面向开关、调制、混频、整流及其他二极管加载结构。参数来自当前工程；不预设特定器件拓扑、源布局或频段。

1. 明确结、封装与三维结构各自表示的物理部分，先读[加载与接口](references/loading-and-interfaces.md)，列寄生归属表，避免重复计入或遗漏。
2. 核对真实 A/K、端口正负、引脚、参考地、参考面及阻抗，验证偏置与交流回路。使用实际 VAK=VA−VK 和电流，不用源值替代。
3. 几何加载按 [cst-modeling](../cst-modeling/SKILL.md)预览审阅，电路配置按 [cst-circuit](../cst-circuit/SKILL.md)。接口改变后检查矩阵有效性。
   导入 CAD 后先 inspect 实际 component:solid、材料和包络，建立源对象到目标对象映射，
   再执行改名、赋材、变换和阵列复制。导入器可能改变组件名；不得拼接预计名称后直接
   批量提交。缺失或重名在只读预检阶段定位，不靠写入失败试探对象身份。
4. 低频/DC、网格、拟合、HB/瞬态和工作点按[数值判断](references/numerical-validity.md)检查；误差与资源预算由当前任务给出。
5. 记录模型来源、参数读回、接口表、实际端电压/电流、运行身份和未验证项。评估器件性能时，将实际 VAK(t) 曲线与对应指标图一起交付；指标与选图用 [cst-device-characterization](../cst-device-characterization/SKILL.md)。

加载成功、偏置建立、数值充分和器件性能分别判定。分析已有结果时不新增求解，数据不足就列缺项。
