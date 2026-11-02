---
name: cst-modeling
description: Use when planning, previewing, creating, or changing CST geometry, materials, boundaries, or ports through cst-automation.
---

# CST 通用建模

真实操作先用 [cst-sessions](../cst-sessions/SKILL.md)。参数取自目标工程及当前输入，不从插件或旧案例推断设备尺寸。

1. 核对坐标、单位、材料、边界、端口、源工程及输出工程，优先 cst_solver 已有 Python API，先查实际签名与能力。
2. 新建或实质改变几何前，用同一组真实参数生成等比例预览，标出轮廓、层叠、端口、关键尺寸和方向，等待审阅。已批准范围持续有效。
3. 按依赖阶段修改、rebuild、读取实际消息，记录实体、端口映射和产物。中断先查原阶段，不重放完整设备。
4. 复杂材料核对张量分量、符号、坐标轴、实体赋值及求解器兼容性；材料存在或宏显示默认值不证明系数读回正确。
5. 参数公式和说明按实际 API 分开传递，保留既有名称及依赖；保存后核对当前工程，不擅自重命名参数。

结构预览用 [cst-figures](../cst-figures/SKILL.md)；二极管实体/集总接口用 [cst-diode-loading](../cst-diode-loading/SKILL.md)。重建通过只建立几何证据。
