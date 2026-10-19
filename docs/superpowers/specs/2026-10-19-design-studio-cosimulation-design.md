# CST 三维电磁结构—Design Studio 场路联合仿真扩展设计（待审阅）

日期：2026-10-19。状态：**用户已批准先实施接口与离线验证；真实三维预览待审阅，实机建模/求解尚未授权启动**。

本轮只读检查仓库源码、本机 CST 2026 的 SDK 源文件和官方帮助，并编写规划文档。没有连接 CST 会话、创建工程、修改几何、占用求解器或执行实机验收。文中的接口均为拟新增接口。

## 1. 目标与建议范围

目标：在通用 `cst-automation` 中实现三维电磁模型与 Design Studio 原理图的连接、配置、运行、结果读取和证据记录，继续保持与 TPC、em-enclosure 无关。

建议分阶段交付，但最终验收同时覆盖以下两种模式：

| 模式 | 数据流 | 可宣称的能力 |
|---|---|---|
| `network` | 三维电磁求解 → 多端口网络 → DS 电路任务；网络可被复用 | 三维电磁网络与电路协同计算 |
| `transient_cosim` | CST 瞬态电磁求解器 ↔ DS 电路求解器，通过实际端口交换量耦合 | 瞬态双向场路联合仿真 |

普通 DS 瞬态任务也可能基于拟合后的电磁网络运行，并产生非线性谐波；它不自动等于 `transient_cosim`。场结果组合也必须与双向耦合分开记录。

第一条主线采用**同一 CST 工程的三维模型与其原理图**，识别并复用实际存在的三维模块。外部三维工程链接随后加入，并逐模式验证。首轮元件范围为 R/L/C、外部端口、接地/参考节点、电压/电流激励、探针、一个二极管及一个小型 SPICE 子电路。暂不承诺完整元件库、任意 SPICE 方言、IBIS、谐波平衡、SAM 多个三维模块的组合、远程集群或多版本 CST 认证。

## 2. 当前依据与待实机确认事项

### 已从当前仓库确认

- `setup` 已有独立会话、attach、工程保存/关闭和通用建模能力；`ProjectMixin.new_project(project_type)` 可接受 CST 工程类型。
- `SolverMixin.run()` 调用 `cst_file.model3d.run_solver()`；现有 `run_checked()` 不是 DS 指定任务的运行入口。
- `Result` 固定选取 `ProjectFile.get_3d()`，不能直接承担电路结果读取。
- `RunService` 只有 `build`、`solve`、`study` 三种任务，由唯一 worker 串行执行，允许显式注册 handler。
- `copy_project()` 当前复制 `.cst` 与同名目录，未提供外部 CST/SPICE/Touchstone 文件依赖闭包和链接重定位。
- 现有结果指纹可提供辅助信息，但工程文件或无关三维结果更新不足以证明目标电路任务成功。
- 本包实机验收状态仍以 `docs/VALIDATION.md` 为准；本轮未提高验证等级。

### 已从本机 CST 2026 官方帮助确认的接口依据

| 官方对象/入口 | 规划用途 |
|---|---|
| `Project.schematic` | 访问关联原理图；文档说明无原理图时可为 `None` |
| `schematic.Block` | 创建、选择、查询元件与属性 |
| `schematic.ExternalPort`、`schematic.Net`、`schematic.CircuitProbe` | 电路端口、网络连接和电压/电流探针 |
| `schematic.SimulationTask` | 创建任务，设置属性，查询并执行指定任务 |
| `SimulationTask.Update()` | 更新指定任务及子任务 |
| `schematic.UpdateResults()` | 更新所有任务；默认不采用，以免误运行其他任务 |
| `schematic.execute_vba_code()` | 对 SDK 未暴露的功能，在原理图上下文内执行经封装的 VBA |
| `ProjectFile.get_schematic()` | 保存后读取 DS 结果域及其 run ID、参数组合 |

本机官方任务帮助列出 `s-parameters`、`dc`、`ac`、`transient` 等类型；瞬态任务的 `circuit simulator` 属性包含 `cosimulation`。官方 Block Types 列出 `CSTMWS`、`CSTMWSFile`、`SPICE`、`SPICEImport` 等类型。以上是**文档依据，不是本包的调用验证**。

实施第一阶段仍需确认：Python 动态对象实际可用方法、CSTMWS 自身模块的识别方式、外部链接属性与读回、引脚/端口/模态映射、激励属性、任务状态/结果归属、求解器和许可证可用性。无法可靠查询的字段应报告 `unknown`，不能从“安装了 CST”推断许可证或联合求解可用。

## 3. 路线选择

| 路线 | 优点 | 限制 | 建议 |
|---|---|---|---|
| 官方 Python 对象优先，缺口由原理图 VBA 适配 | 有官方教程依据；易测试与读回；复用现有会话 | 部分动态接口和版本差异需实测 | **主方案** |
| 从 CST 内置/人工审核模板复制后修改 | 可较快建立可信实机基线 | 模板不能替代通用建图接口，易隐藏链接/单位 | 用于独立参考与诊断 |
| 全程 GUI 自动化 | 可以处理缺少 API 的少量操作 | 难稳定复现、难独立查询连接 | 仅用于观察与必要的参考工程准备 |

不把任意 VBA 文本作为 MCP 公共写接口。经批准的操作由底层适配器产生固定命令，在服务 worker 内执行，并记录实际调用与读回。

## 4. 拟新增接口

保留 `setup.run()`、`setup.run_checked()`、`Result(path)` 现有行为。新增 `setup.circuit` 惰性 facade；普通导入、读取 schema 或生成预览不导入 CST SDK、不启动 CST。

另提供 `cst_solver.circuit.circuit_capabilities(*, probe="static", app=None) -> dict`，使静态能力发现无需先实例化 `setup`。`probe="live"` 必须使用显式传入的已连接 `app`；不悄悄启动新会话。`app.circuit.capabilities()` 委托该入口。

### 4.1 公共数据与离线预览

放在 `cst_automation.circuit_schema`，只依赖标准库，使用可 JSON 序列化的规格：

- `validate_circuit_spec(spec: dict) -> dict`：校验类型、重复名称、属性类型、量纲、表达式引用和规格版本。
- `preview_circuit(spec: dict, output_dir: str) -> dict`：输出 SVG 原理图、端点连接表、参数表和源规格摘要；不调用 CST。
- `CircuitSpec` 的顶层字段固定为 `schema_version=1`、`units`、`parameters`、`blocks`、`external_ports`、`nets`、`probes`、`em_links`、`tasks`。

每个 block 包含 `name/type/properties/property_units/position`；每条 net 包含 `name/endpoints`。端点以 `component_kind/component_name/pin_name` 表达；三维映射还记录 `port_id/mode/reference/polarity`。这些名称属于本包 schema，不能直接假设等同于 SDK 的索引。

物理数值使用显式单位或带量纲的参数表达式。内部校验按 SI；写入 CST 时转换到明确的项目/属性单位。原理图布局坐标使用独立整数网格，不得当作三维毫米坐标。重名、悬空、缺参考、非法单位和跨域参数冲突均应在写入或求解前说明。

### 4.2 工程、能力和原理图

| 拟定签名 | 返回与用途 |
|---|---|
| `setup.new_circuit_project()` | 新建 DS 工程；由已有 `new_project` 路径实现，实测 DS 工程类型 |
| `app.circuit.capabilities(*, probe="static") -> dict` | 报告文档/SDK发现、实机读回和各模式验收状态；`live` 显式触发连接检查 |
| `app.circuit.inspect() -> dict` | 实际工程类型、blocks、pins、nets、任务、参数、单位、探针和链接 |
| `app.circuit.list_block_types() -> list` | 返回适配器已明确支持的类型，附版本/证据；不冒充完整实时元件库 |
| `app.circuit.list_pins(block_name: str) -> list` | 实际 pin/port 名、索引、参考、方向、可映射的三维端口/模态 |
| `app.circuit.apply(spec: dict, *, conflict="error") -> dict` | 校验后写入规格并读回；默认遇到同名已存在对象即报错 |
| `app.circuit.set_properties(block_name: str, properties: dict, *, units: dict) -> dict` | 修改元件属性/参数，返回读回和受影响任务 |
| `app.circuit.validate(*, task_name: str) -> dict` | 求解前检查目标任务、拓扑、引脚、模型文件、带宽和耦合模式 |

`apply` 在单次服务 build 中按“单位/参数 → 三维模块 → 元件/端口 → 网络 → 探针 → 任务”写入。首次只支持 `conflict="error"`，不自动删除用户原理图。部分写入失败时保留工作副本和阶段证据，标为部分构建失败，不承诺 CST 事务回滚。

低层 blocks/nets/tasks 操作先保持实现细节；不同时向包根平铺大量函数。已有波导/离散端口创建接口继续复用，但**连接必须依据实际端口与 pin 读回**。不同 SDK 对象的索引可能从 0 或 1 起，适配器分别处理，禁止统一减一猜测。首个瞬态样例使用官方示例采用的离散端口；其他端口/模态按能力表逐项开放。

### 4.3 三维模块链接与依赖

| 拟定签名 | 约束 |
|---|---|
| `app.circuit.link_em(*, block_name: str, source: str, port_map: list, parameter_map: dict) -> dict` | `source="self"` 复用当前实际三维模块；其他值为显式工程路径；校验后读回 |
| `app.circuit.inspect_dependencies() -> dict` | 枚举 CST 工程、同名目录、子链接、SPICE、Touchstone 等依赖与缺失项 |
| `app.circuit.bundle(destination: str) -> dict` | 复制依赖闭包到工作区、改写受支持的相对链接、输出 manifest、重开检查 |

manifest 记录来源、工作副本、逻辑链接、相对路径、SHA-256、端口/参数映射和未解析依赖。CST/SPICE 循环引用、缺文件、同名碰撞和当前无法解析的间接引用须明确失败；首次不实现任意第三方格式解析器。外部依赖原件只读，复制/重定位产物都在仓库 `work/` 中。

输入配置摘要与结果文件散列分开维护：前者来自可重建的几何/材料/网格/端口/电路/任务配置，后者用于结果完整性。不能把求解后自身会变化的整个 `.cst` 散列直接作为下一次缓存配置键。若无法完整读回影响计算的配置，该输入不得获得 verified 缓存复用资格。

三维模型、网格/材料/端口配置改变：使相关电磁网络与下游任务失效。电路 RLC/激励改变：使相应电路任务失效；`network` 可显式复用经指纹核验的三维网络；`transient_cosim` 必须重新执行耦合任务。端口映射或三维参数映射改变：两侧依赖都重新核验。

### 4.4 任务运行与证据契约

拟定签名：

`app.circuit.run_checked(task_name: str, *, mode: str, expected_results: list, reuse="never", note="") -> dict`

- `mode` 仅允许 `network` 或 `transient_cosim`；普通瞬态网络计算仍标为 `network`。
- 只运行指定任务与其必要依赖，调用选定任务的 `Update()`。预检读取真实任务属性，与请求模式不符时失败。
- `reuse="never"` 为验收默认，必须验证目标任务本次被执行；`reuse="verified"` 只能用于显式识别的缓存，记录源运行和配置摘要，不能声称本次重新求解。
- 显式保存工程及结果后，从相应结果域读回。三维和电路消息读出后立即持久化，不靠“消息为空”单独判成功。
- 不改变现有三维运行契约；新增 `cst_solver.circuit.run` 实现任务级验收，复用日志、错误结构和弹窗诊断组件。

至少记录以下身份与证据：

| 字段 | 内容 |
|---|---|
| `run_token` | 本包一次运行的唯一标识 |
| `task_name/task_type/mode` | 实际执行的任务及仿真模式 |
| `project_identity` | 工作副本路径、输入规格/配置摘要、CST 版本/build、依赖清单 |
| `em_runs/circuit_runs` | 两侧各自的结果域、实际 run ID/参数组合与可获取的完成证据 |
| `expected_results` | 真实树路径、任务归属、run ID、量纲、采样区间和数据摘要 |
| `stage_evidence` | 三维读回、原理图读回、目标求解、保存、结果读取、数值对照分开记录 |
| `cache` | 是否复用、复用的来源、失效判定依据 |

`succeeded` 必须同时满足：目标任务确已完成或显式核验缓存、实际模式符合请求、没有致命求解错误、完成保存、指定必需结果能读出且归属正确。恒定的计算结果也可以成功，不强制“数值必须改变”；修改文件时间、整工程指纹变化或别的任务更新均不足为据。无法取得任务身份/完成证据时返回 `unverified`。

运行超时且 SDK 未返回时，服务继续占用该串行 worker 并报告诊断；不启动第二次同工程写操作，不把它冒充已取消。弹窗只依据实际标题、正文、按钮、PID 与预先批准策略处理。现有结果失效删除提示须记录范围；仅允许对本次工作副本中预期的失效结果操作。

### 4.5 电路结果

新增 `CircuitResult(path)`，内部选取 `ProjectFile.get_schematic()`；不通过继承暴露三维场/远场等不适用方法。

| 拟定签名 | 用途 |
|---|---|
| `get_tree_items(*, task_name=None) -> list` | 列出保存工程中的实际电路树项 |
| `get_run_ids(tree_path: str) -> list` | 查询该树项真实可用运行，禁止统一假定为 0 |
| `get_parameter_combination(run_id: int) -> dict` | 查询该电路结果域的参数组合 |
| `read_curve(tree_path: str, *, run_id: int) -> dict` | 返回 x、y、单位、实数/复数、任务/运行身份和来源 |
| `export_csv(tree_path: str, destination: str, *, run_id: int) -> dict` | 保存电压、电流、S 参数、频谱或功率的曲线与元数据 |

首次以实际树路径读取，避免猜测 CST 自动生成的探针/任务名称。缺项、错运行、无法解码、单位不明均返回明确错误，不取旧结果替补。CSV 中复数实/虚部分列；电压幅度、峰值/RMS、功率参考、探针电流方向与 FFT 窗口必须在元数据中说明。

## 5. 服务和 MCP 接入

保留 `build/solve/study` 和现有任务状态。新增显式注册函数 `register_circuit_handlers(service)`，为这三类任务安装路由：仅 `params.workflow="circuit"` 进入电路实现，其他任务委托已注册 handler/原 backend。默认不替换已有 handler；显式安装时保存并组合旧实现，禁止静默覆盖领域 handler。

- `build`：创建/配置原理图并保存，不启动求解。
- `solve`：运行指定任务并保存/验收。
- `study`：实现小规模 RLC/激励参数序列；唯一 worker 顺序执行，记录每点身份；失败停止后续依赖点。
- 读回和副本打包等需访问 CST 的操作也提交 worker；不得从 MCP 主线程直接接触 SDK 句柄。静态 schema/离线文件读取可直接处理。

路由同时要求 `params.operation`：`build` 接受 `configure/inspect/read_results/package`，`solve` 接受 `run_task`，`study` 接受 `parameter_sequence`；未知组合在调用 SDK 前拒绝。只读的 inspect/read_results 仍可使用 build 队列，但不构建几何、不求解，证据明确标为只读；未保存现场不能标记 `saved=True`。向现有服务提交前必须已有显式登记的磁盘工作工程；新 DS 工程可先通过 Python 工程入口创建并保存，再登记。

电路契约 `unverified` 在现有服务状态中映射为 `failed`，错误码 `circuit_result_unverified`，同时保留具体证据状态；不悄悄新增持久化任务状态。失败/中断同样保留已产生的日志、身份和产物。扩展 `fail_result` 的可选证据字段，旧调用默认值不变。MCP 的失败证据通过现有状态/产物接口可查，不称为成功结果。

拟定专用错误码为 `circuit_unavailable`、`circuit_spec_invalid`、`circuit_topology_invalid`、`circuit_mode_unsupported`、`circuit_dependency_missing`、`circuit_build_partial`、`circuit_result_unverified`、`circuit_result_read_failed`。错误应附阶段、对象/属性、原始 SDK 异常与产物路径。弹窗/超时沿用现有诊断字段，不用新错误码掩盖 SDK 尚未返回的事实。

新增 `cst_mcp.circuit_tools.register_circuit_tools()`，明确注册以下工具：

| 工具 | 行为 |
|---|---|
| `preview_circuit` | 离线校验和输出预览产物，作为文件写操作标注 |
| `inspect_circuit` | 排队执行只读 SDK 检查，返回任务号 |
| `configure_circuit` | 排队构建/配置并保存 |
| `run_circuit_task` | 排队执行指定模式/任务 |
| `read_circuit_results` | 排队读取保存结果并导出到受限工作目录 |
| `package_circuit_project` | 排队复制/重定位依赖并读回 |

现有 `get_capabilities` 增加可选电路能力区块；静态发现不打开工程。所有 CST 写操作遵守 `RunService`，显式注册、JSON schema、路径限制和幂等 request ID 继续有效。

先更新 `docs/PUBLIC_API.md` 再改跨包协议；计划发布为 `0.2.0`，兼容现有默认行为和 `>=0.1,<1` 消费者。不修改相邻仓库、全局 MCP 配置或公共 Python 环境。

## 6. 实机验证设计

### 6.1 统一规则

- 仅在本仓库 `work/circuit-validation/<run>/` 中新建或复制工程；CST 安装资料、用户工程、迁移源保持只读。
- **实施阶段先按真实参数生成三维几何预览、端口位置表和电路连接图，交用户审阅后再建模。** 本文参数是候选验收规格，不是已经审阅的几何。
- 环境记录 CST 年份/build、Python/SDK、许可证请求结果、线程/GPU、网格、边界、端口、材料、激励、频率/时间窗口；没有验证的项目保持 unknown。
- 先 UI/官方参考基线，再 API 构建的独立副本；二者输入参数必须相同。参考工程也在 `work/` 中，记录来源、散列及读回，不能用同一导出函数的结果互相“验证”。
- 单阶段不通过就保留现场和证据，停止其依赖的求解。首次小模型限制目标网格不超过 20 万单元、单次求解诊断阈值 10 分钟；超限先评估/缩小基准，不自动开启大规模或高资源求解。阈值到达不等于强制停止成功。
- 容差在运行前冻结。失败后不能通过放宽阈值把结果改判通过；需解释原因、修改规格并保留前后记录。

### 6.2 验证矩阵

| 阶段 | 样例与操作 | 验收重点 | 证据级别 |
|---|---|---|---|
| V0 | `.venv` 中离线测试、打包、独立导入 | schema、命令路由、单位、引脚索引、失败记录、兼容性；不加载 CST | offline |
| V1 | CST 2026 专属会话；纯 DS 串联 RLC 二端口 | 创建/读回元件、网络、探针、任务；保存关闭重开后完全一致 | circuit readback |
| V2 | RLC 二端口 S 参数任务和纯电路瞬态任务 | 目标任务完成、结果归属、解析参考、UI/API 对照 | circuit solver |
| V3 | 小型三维传输线 + DS 线性负载，`network` | 三维模块/端口映射、S 参数网络与电路连接、加载响应 | network solver |
| V4 | 同一三维模型 + 线性 RLC，`transient_cosim` | 真实耦合模式、两侧完成与端口交换证据、波形/负载变化 | transient cosim solver |
| V5 | 同一模型 + 二极管，随后替换为一个已知 SPICE 子电路 | 非线性响应、幅度依赖、谐波、两侧证据与收敛 | nonlinear cosim solver |
| V6 | 外部三维链接/模型文件打包；移动到新的工作目录再开 | 无原路径依赖、链接与映射保留、重算/读回一致；按模式分别验收 | portability |
| V7 | A→B→A 参数变化、缓存、损坏映射、缺模型、重启恢复 | 过期结果被拒绝；失败可追溯；运行未完成不提升为成功 | robustness |

### 6.3 纯电路定量基准

V1/V2 候选：50 Ω 两端口之间串联 RLC，R=10 Ω、L=10 nH、C=1 pF；频率 0.1–3 GHz，301 个显式频点。元件和参考阻抗均理想，先排除模型差异。

解析基准取 `Z=R+jωL+1/(jωC)`、`S21=2Z0/(2Z0+Z)`、`S11=Z/(2Z0+Z)`，谐振约 1.59155 GHz。要求全频带最大复数 S 误差 ≤1e-3；以扫描最小阻抗/最大传输定位谐振时，偏差 ≤一个频点间距。UI 与 API 相同设置下最大复数 S 差 ≤1e-6。纯电路瞬态另外固定电源内阻、初值和采样时间，与独立 RLC 状态方程积分比较，归一化 RMS 电压误差 ≤1%。

改变 C 为 2 pF 后执行，必须读出新参数组合、谐振下移；恢复 1 pF 后重算允许数值回到原值。该测试既检查参数生效，也避免“结果数值不变就一定未运行”的错误规则。

### 6.4 三维和线性联合基准

V3/V4 候选为两端离散端口的短微带线：基板 20×10×0.8 mm，εr=2.2、无损；顶层线宽 2.4 mm、长 20 mm；金属厚 0.035 mm，首次采用 PEC。端口跨接信号线与地；周围空气与开边界、端点坐标、网格方案在实施前的真实几何预览中明确。此几何**不预先宣称恰好 50 Ω 匹配**；50 Ω 仅为端口参考。

先对裸线提取完整复数 S 网络。DS 加入 RLC 或 25/50/100 Ω 负载，使用同一参考阻抗独立计算加载响应，再与 DS 结果比较：最大复数响应误差 ≤0.02；对幅度 >0.1 的传输项，相位误差 ≤3°。涉及功率时，用一致的波变量和归一化核算输入、反射、输出、损耗/辐射，而非把所有电压比当作 S 参数。

V4 先用线性负载、1 GHz 正弦启动激励：Thevenin 源峰值 1 V、内阻 50 Ω，启动包络 2 ns，Tmax=40 ns，稳态窗口 20–40 ns。必须记录实际结束时间；官方帮助说明 MWS 能量衰减判据可能导致耦合任务提前结束，未覆盖窗口即失败或调整停止设置后重新验证。输出采样间距与求解器内部时间步分别记录；要求输出间距 ≤5 ps，内部步长进一步受 CFL/误差控制约束。

在线性条件下，与通过已核验三维网络得到的参考稳态电压/电流比较，幅值误差 ≤3%、相位误差 ≤3°。非周期激励的瞬态比较只在带宽、低频/DC 行为、拟合精度及初值均受控时启用，不能用不充分带宽的网络强行当参考。25/50/100 Ω 负载改变后，应同时在电路探针和三维输入端口的反射/电流中读到一致变化。

### 6.5 真正双向耦合与非线性验收

V4/V5 必须保留以下相互独立的证据，缺失时不标记“瞬态双向耦合已验证”：

1. 从真实任务读回瞬态类型及 `circuit simulator=cosimulation`，并确认实际链接/离散端口，而非仅保存请求参数。
2. 本次 DS 任务与所依赖的瞬态三维运行均有完成记录、归属或可验证执行日志；不能只看一个文件更新时间。
3. 两侧端口电压/电流、三维局部探针与电路波形对应；改变负载后重新耦合运行并观察反馈。端口方向/参考约定统一。
4. 以普通网络瞬态计算作对照，明确其模式与结果。非线性谐波、场组合或两侧曲线相似都不能单独区分求解架构。

V5 候选拓扑为：三维线输出 → 10 Ω 电阻 → 串联二极管 → 输出节点，输出节点以 1 kΩ 与 1 pF 并联接地；探针记录二极管 I/V 和输出电压。先用内置二极管，源峰值从 0.1 V 改为 1 V，保持定义、内阻与其他参数一致；随后用显式固定 A/K 引脚顺序的简单 SPICE 子电路做复测，不下载未知模型。候选二极管模型为 `IS=1e-14 A, N=1, RS=1 Ω, CJO=0 F`；内置元件与 SPICE 对应关系须读回确认，无法对齐时分别对各自 UI 基准比较，不宣称二者器件等价。

三维设置至少覆盖基频与第三谐波，候选带宽 0.1–5 GHz；非线性基准关注稳态，不把该网络带宽宣称为 DC/任意脉冲精确模型。

比较二极管 I–V、整流/DC 分量（若输出拓扑提供）、基波及二/三次谐波。与同一配置的独立 UI 基准相比，稳态电压 NRMSE ≤3%；幅度高于 -40 dBc 的谐波幅度偏差 ≤5%。采用共同时间网格、同一窗口和相同峰值/RMS convention，去除预定义启动区，禁止自由平移波形来掩盖时延。

分别进行“加密网格、保持时间设置”和“减小内部最大步长、保持网格”的复测；每次稳态基波幅值变化 ≤2%，上述可测谐波幅值变化 ≤5%；不满足时只报告未收敛。KCL/端口电流方向检查为必需；若官方接口能导出全部必要能量项，再做包含储能变化与辐射/损耗的能量平衡，缺项时不声称已验证能量守恒。

### 6.6 失效与可搬运性

- 三维几何、端口编号/极性、材料或电路参数修改后，测试依赖失效和模式匹配；错 pin/缺参考/断线应在求解前失败。
- 移走一个工作副本内的 SPICE 文件，必须返回具体缺失依赖；恢复后才允许重试。
- 复制打包工程到第二个 `work/` 子目录；结构化读回每个受支持链接的实际解析路径，要求均在新副本目录内，不使用删除/改名原始用户目录来证明隔离。未能完整查询的依赖不计为搬运验证通过。重开并重算，与基准比较。
- 验证重复 request ID 不重复执行；服务重启只标记 interrupted，不自动重跑；attach 不关闭用户会话。
- 弹窗先离线注入测试；实机仅记录自然出现或可控小副本中的提示，不主动制造破坏性操作。SDK 阻塞时禁止并发补发写操作。

## 7. 交付与完成判据

每阶段产物目录至少包含 `environment.json`、输入规格、预览、`dependencies.json`、CST 保存工程、实际读回、任务/运行日志、消息/弹窗记录、结果 CSV+元数据、对照和误差报告。截图仅辅助，关键连接和参数须结构化读回。

实施交付包括：新增 Python/API 与类型声明、显式 service/MCP 注册、离线测试、实机 opt-in 验证脚本、使用示例、公共协议和验证文档。实机脚本不进入默认测试流程；须显式标记并受样例/资源限制。

只有 V4/V5 分别通过，才能分别声明线性/非线性瞬态联合求解已验证；V6 要按实际通过的模式说明支持范围。阶段性通过可单独交付，但不能把 V2/V3 通过描述成最终双向联合仿真支持。

## 8. 本机与官方参考

本机检查来源（只读）：

- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/Python/source/cst.interface.html`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/Python/source/cst.results.html`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/PythonTutorial/circuit_simulation_creating_connecting_blocks.html`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/PythonTutorial/circuit_simulation_task_definition.html`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/PythonTutorial/circuit_simulation_results.html`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/mergedProjects/VBA_DES/special_vbacommands/blockobject.htm`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/mergedProjects/VBA_DES/special_vbacommands/blocktypes.htm`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/mergedProjects/DES/analysis/simulation/tasks/transient_simulation_task_settings.htm`
- `C:/SOFTWARE/CST Studio Suite 2026/Online Help/mergedProjects/EXP_DES/transient_circuit-em_co-simulations/examples/balanced_amplifier_transient_cosimulation.htm`

公开官方说明：[Dassault Systèmes：Electromagnetic Design Environment / EM-Circuit Co-Simulation](https://www.3ds.com/products/simulia/cst-studio-suite/electromagnetic-design-environment)。该页确认 CST 产品具备包含 SPICE/非线性器件的瞬态场路联合能力，不证明本包或本机许可证已经验收。
