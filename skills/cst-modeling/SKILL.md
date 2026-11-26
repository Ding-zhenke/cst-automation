---
name: cst-modeling
description: Plan, preview or edit CST solids, curves, materials, boundaries and ports. Use also for read-only inspection of discrete-port coordinates, impedance and length.
---

遵守[完整阅读规则](../README.md#完整阅读规则)。

# CST 建模

查看既有端口坐标、阻抗或长度时，直接从[只读检查离散端口](#只读检查离散端口)开始。实际工程操作使用[所属会话](../cst-sessions/SKILL.md)。有可复现的建模 Python 时，默认以它为源，先按当前 API 和 CST 版本修改几何、拓扑、参数、材料、边界或端口，再在所属会话用 `create_project` 从空工程分阶段构建。无代码的新设计也从空工程开始并保留建模 Python。改变结构构造步骤时保留旧工程/结果作参考，在生成器内修改对应轮廓或实体，让新历史记录最终设计。

用户明确要求续改、恢复或读取指定工程，或存在无法从源码重建的内容时，使用原工程。明确保留原工程的同拓扑参数、材料、网格与扫描更新复用原 project_id、worker 和 DE。求解、读取和扫描准备按各自授权执行，保持输入身份；调用失败先查原任务。

## 操作与审阅

提交建模写入前读 [API 操作与参数语义](references/api-selection.md)，并检查当前运行库的
模块路径、真实签名和会话白名单。列出本次对象、采用的 API、输入参数与依赖阶段。
API 生成 VBA 是正常实现；调用方重新拼接已有 Brick/Cylinder/Transform 等命令是绕过
API。不得用自拼原生命令代替已有 API 来完成整台设备。若已有可复现建模 Python，整机
修改仍以修改该源代码并从空工程重建为首选。会话未路由已有方法时补显式路由；确实
没有封装的可复用操作才补 API。最小原生命令只用于有依据的真实缺口，需说明缺少什么。

设计或修改领域器件的晶格、相位、拓扑或器件结构时，同时加载可用的领域 skill。TPC 加载 `topological-modeling`
及相关晶格/模板技能，让领域包决定晶格、相位和路径；本包负责通用 CST 操作，不
引入领域包依赖。不能因为底层都调用 CST 就跳过领域建模规范。

- 建模、改参或提交几何前，必读[参数预览与分阶段构建](references/geometry-review.md)。以同一组真实参数作等比例预览，等待审阅；保留表达式、依赖、单位、工况、几何检查及阶段验收证据。
- 创建实体或曲线成体、改变材料赋值前，必读[材料前置检查](references/port-material-review.md#材料前置检查)：列出所有将引用的材料名，在当前工程先创建或导入缺失材料并检查该阶段回执与 CST 消息，再提交依赖几何。几何 API 的 `material=` 只引用名称，不会自动定义材料；空工程不能继承其他工程的材料。
- 设置材料或边界时，读[物理表示与边界](references/port-material-review.md#物理表示与端口审阅)及[材料与单位](references/model-operations.md#材料与单位)或[边界与背景](references/model-operations.md#边界与背景)。改变参考或端接阻抗时先区分[阻抗的含义](references/port-material-review.md#阻抗与匹配)。

## 创建或替换端口

先按[真实参数预览](references/geometry-review.md#参数与几何审阅)标出端口编号、截面或两条接触边、方向、模式和参考面，等待审阅。在所属工程按[端口创建与替换](references/model-operations.md#端口创建与替换)选对应 API 和 worker 能力；板端馈电或有限宽度焊盘追加[微带接触边](references/model-operations.md#微带接触边)。替换前归档所需结果并记录目标及保留端口，完成后核对实际类型、属性、端点或模式数，以及保留端口。建模交付止于本次写入、保存与可取得的原生读回。

## 只读检查离散端口

按[离散端口原生只读](references/model-operations.md#离散端口原生只读)向原工程所属会话提交 `inspect`，传入请求的 `discrete_port_ids`。交付工程身份、端口编号、请求的实际坐标、阻抗或几何长度、单位和查询错误。已有明确匹配工况的读回回执也可直接查阅。只读流程在取得请求项或定位缺失字段时结束，无需预览、重建、生成缓存或求解。

## 设置与验收

选择或改变网格、频带、自适应策略时读取 [cst-mesh-frequency](../cst-mesh-frequency/SKILL.md)，
只选当前求解器对应章节。配置扫描时使用 [cst-parameter-study](../cst-parameter-study/SKILL.md)；
实际求解时使用 [cst-simulation](../cst-simulation/SKILL.md)。仅建模或沿用已审阅设置时不预加载这些流程。

每个依赖阶段保留稳定 stage_id/request_id，重建、读实际消息，再用 inspect 核对参数、
实体、材料、体积和关键点；端口/设置使用相应真实读回能力。缺读回就保留未验证，不
用 history 调用成功代替。是否补界面检查取决于该字段是否影响当前判断或属于明确交付项；
不为消除所有 unverified 标记逐项截图。关键材料、激励或设置存在矛盾时须查清后再依赖它。
超时查原任务与现场，不复制/重放未知阶段。探测输出在 Python
写报告，不污染模型回放历史；弹窗按实际标题、正文、按钮和进程归属诊断。

历史错误优先按 [cst-diagnostics](../cst-diagnostics/SKILL.md) 通过任务回执、异常、
CST 消息和弹窗文本定位并修正源代码，Computer Use 仅在文本不可读或程序化处理
不足时使用。空工程也会因无效命令报错；不能跳过失败历史或屏蔽错误来宣称构建成功。

交付原工程最终 CST、必需配套目录、可复现建模 Python 和所需 PNG；阶段副本、备份、
额外矢量格式和压缩包按用户需求提供。建模收尾时按下述规则清理过程工程，保留工作 DE。
分别报告配置提交、原生读回、几何重建、实际求解和数值收敛；不以其中一项代替另一项。

## 建模结束后的过程文件清理

建模任务结束、正式 CST 及配套数据和依赖核验通过后，按[工程交付与过程工程清理](../cst-project-lifecycle/SKILL.md)主动收尾。通过所属会话保存、关闭、退休本任务已完成用途的过程工程，核对回执和路径后删除，包括登记为 `working` 的过程副本。仍在使用、状态不明或用户指定保留的工程继续保留。
