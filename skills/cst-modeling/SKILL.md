---
name: cst-modeling
description: Use when planning, previewing, creating, changing or checking CST solids, curve profiles, boolean operations, transforms, picks, coordinates, materials, boundaries or ports through cst-automation.
---

遵守[完整阅读规则](../README.md#完整阅读规则)。

# CST 建模

实际工程操作先读[所属会话](../cst-sessions/SKILL.md)。有可复现的建模 Python 时，默认以它为源，先按当前 API 和 CST 版本修改几何、拓扑、参数、材料、边界或端口，再在所属会话用 `create_project` 从空工程分阶段构建。无代码的新设计也从空工程开始并保留建模 Python。改变结构构造步骤时保留旧工程/结果作参考，在生成器内修改对应轮廓或实体，让新历史记录最终设计。

用户明确要求续改、恢复或读取指定工程，或存在无法从源码重建的内容时，使用原工程。明确保留原工程的同拓扑参数、材料、网格与扫描更新复用原 project_id、worker 和 DE。求解、读取和扫描准备按各自授权执行，保持输入身份；调用失败先查原任务。

## 操作与审阅

在提交前读 [API 操作与参数语义](references/api-selection.md)，并检查当前运行库的
模块路径、真实签名和会话白名单。列出本次对象、采用的 API、输入参数与依赖阶段。
API 生成 VBA 是正常实现；调用方重新拼接已有 Brick/Cylinder/Transform 等命令是绕过
API。不得用自拼原生命令代替已有 API 来完成整台设备。若已有可复现建模 Python，整机
修改仍以修改该源代码并从空工程重建为首选。会话未路由已有方法时补显式路由；确实
没有封装的可复用操作才补 API。最小原生命令只用于有依据的真实缺口，需说明缺少什么。

任务属于领域器件时，同时加载可用的领域 skill。TPC 加载 `topological-modeling`
及相关晶格/模板技能，让领域包决定晶格、相位和路径；本包负责通用 CST 操作，不
引入领域包依赖。不能因为底层都调用 CST 就跳过领域建模规范。

- 建模、改参或提交几何前，必读[参数预览与分阶段构建](references/geometry-review.md)。以同一组真实参数作等比例预览，等待审阅；保留表达式、依赖、单位、工况、几何检查及阶段验收证据。
- 设置材料、边界、端口或改变阻抗时，必读[材料、边界与端口](references/port-material-review.md)和[装配、坐标、材料和端口](references/model-operations.md)的对应章节，包括适用的板边馈线、接触边、端口读回或替换流程。

## 设置与验收

求解前读取 [cst-mesh-frequency](../cst-mesh-frequency/SKILL.md)：先估计材料/模式内的
电尺寸和网格成本，再决定 Automatic 行是否参与自适应。大模型通常只选少数 Single
点迭代，小且可负担的模型可用 Automatic 自适应；不能一刀切或只沿用默认 automation。
扫描使用 [cst-parameter-study](../cst-parameter-study/SKILL.md)，明确线性/对数/离散、
工况数、几何约束和网格有效范围。真正求解交给 [cst-simulation](../cst-simulation/SKILL.md)。

每个依赖阶段保留稳定 stage_id/request_id，重建、读实际消息，再用 inspect 核对参数、
实体、材料、体积和关键点；端口/设置使用相应真实读回能力。缺读回就保留未验证，不
用 history 调用成功代替。超时查原任务与现场，不复制/重放未知阶段。探测输出在 Python
写报告，不污染模型回放历史；弹窗按实际标题、正文、按钮和进程归属诊断。

历史错误优先按 [cst-diagnostics](../cst-diagnostics/SKILL.md) 通过任务回执、异常、
CST 消息和弹窗文本定位并修正源代码，Computer Use 仅在文本不可读或程序化处理
不足时使用。空工程也会因无效命令报错；不能跳过失败历史或屏蔽错误来宣称构建成功。

交付原工程最终 CST、必需配套目录、可复现建模 Python 和所需 PNG；阶段副本、备份、
额外矢量格式和压缩包按用户需求提供。建模收尾时按下述规则清理过程工程，保留工作 DE。
分别报告配置提交、原生读回、几何重建、实际求解和数值收敛；不以其中一项代替另一项。

## 建模结束后的过程文件清理

建模任务结束、正式命名的最终 CST 与同名配套数据已核验完整后，必须通过所属会话
保存、关闭并退休本任务的过程工程，再删除对应过程 `.cst` 和配套目录；不遗留
`model.cst` 等过程副本，即使创建时未标记 `lifetime="temporary"` 也适用。
具体回执、路径核对和清理范围遵守[工程生命周期](../cst-sessions/references/project-lifecycle.md)。
任务尚未结束、状态不明或仍有用途的工程继续保留；正式工程、必需依赖、用户指定参考
及其他任务/会话工程不随之删除。回复结束或断线本身不代表建模任务结束。
