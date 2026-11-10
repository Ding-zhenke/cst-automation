---
name: cst-circuit
description: Use when developing or using CST Design Studio circuit schematics, EM port links, network or transient field-circuit co-simulation, circuit results, or their service and MCP interfaces in cst-automation.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# CST 场路联合

参数修改 → EM → HB 的[强制提交检查](../../docs/guides/workflow_enforcement.md)
已接入所属会话；HB 需匹配的成功 EM 回执、已接受数值报告及原生设置读回。
先绑定规格，按回执依次推进，不能靠助手自觉调用可选检查。数值报告来源分析和
未声明的工程判断仍须实际完成；下述低层 API 不得用来绕过受保护工程的会话门槛。

已保存 EM 与 SDK abort 矛盾时，先读[资格核验和网络交接](../../docs/guides/saved_em_qualification.md)。
使用独立资格回执，不改失败任务为成功，不自动解除现场保护或重算。
`fit_em_network/update_hb_network` 用于内置同工程 EM → 同端口顺序的非缓存文件块。
实际低频拟合并原位更新已有内嵌块用 `prepare_hb_embedded_network`，按上述指南提供
完整矩阵、物理端口顺序、原生阻抗和数值门槛；接口独立核对最终网格的真实低频
激励记录、DC 拟合与保存后的有效载荷。内嵌顺序为显式物理矩阵 → 顺序引脚，不能
沿用另一个 EM 块的显示顺序或绕过检查。新操作尚待所属工程实机验收。

实际 Codex 操作先使用[对话持久会话](../cst-sessions/SKILL.md)，配置/求解/在线读回均借用同一会话。

多轮 EM→HB 工作先恢复[要求与证据清单](../cst-sessions/references/workflow-checkpoint.md)，
确认当前源/负载、矩阵、扫描范围和后处理输入，不能只恢复 project_id 就沿用旧默认设置。

使用本仓库的 `app.circuit` 与 `CircuitResult`，区分原理图配置、网络协同计算和瞬态场路联合。仅在三维模型中放置集总元件的任务使用 `cst-modeling` / `cst-simulation`。

先读 [使用指南](../../docs/guides/circuit_cosimulation.md)。开发接口时再读 [公共协议](../../docs/PUBLIC_API.md)；确认实机能力时读 [验证记录](../../docs/VALIDATION.md)，不要从接口存在推断验收通过。

## 当前工作重点

实际工程的几何尺寸、材料与二极管参数、频段、偏置、泵浦及扫描范围属于用户私有产物，
不得从工程中提炼到通用 skill 或示例；可复用流程只保留接口、符号参数和证据要求。

当前以功能完善和可复用工作流为主，见 [开发重点](../../docs/CIRCUIT_DEVELOPMENT.md)。不为了补齐验收矩阵自行启动样例、非线性求解、网格或时间步收敛扫描。后续实际工程中围绕当次目标逐步验证；保留既有门槛和未验证项。修改程序所必需的小范围离线检查可以开展，不把全套实机验收设为每项功能开发的前置条件。

## 选择入口

通用电路设置、读回和任务提交均使用原生 Python/API，必要时使用有依据的 VBA。
缺少能力时报告具体缺失的接口和未完成的设置，不把 Computer Use 作为回退来
配置、运行或绕过任务门槛。真实弹窗的诊断按所属会话规则处理，不把处理弹窗
等同于 API 已支持该功能。

HB 基频/阶数、原生 Parameter Sweep 序列、指定运行的谱线、Results 曲线写入，
以及首次注册、已绑定模板更新，使用 [原生 HB 与后处理接口](../../docs/guides/native_hb_postprocessing.md)。
普通 native 小接口不保存/求解；`register_python_result_template` 是明确会保存关闭重开当前工程的注册接口，仍不求解。

### 原生 HB 双参数扫描：先检查接线再配置

执行指令：用户要求设置 HB 扫描时，直接使用本机 CST、当前工程和下列接口完成配置；不要把索要另一台电脑的 VBA、宏、成功样例或私有工程当成前置条件。先调用所属会话按 `project_id` 取得工程，读任务与源；缺父任务时按指南使用已文档化的 `SimulationTask.Type/Name/Create` 创建 Parameter Sweep，缺 HB 子任务时创建 Spectral Lines 并设为父任务子项；存在时复用，不重复创建。通过 `SetProperty("enabled", "True")` 显式启用父任务与 HB。用户没有授权求解时只配置并保存。

频率与方向绑定由 AI 在目标工程内完成：列出实际外部端口、源块、参数、连接和属性，读取 HB 任务已有频率表达式及实际激励配置；如果绑定缺失，按照该机官方 CST Help 中对应**Spectral Lines** 激励类型的命令写入目标源或端口表达式，并核对每个方向的激励端口及终端。`configure_task_ports` 当前只支持 transient，不能冒充 HB 端口设置；`SetComplexPortExcitation` 文档针对 AC，也不能直接套到 HB。不要根据其他设备猜源名、端口或方向编码。只有用户未提供且工程也无法确定必要的频点、功率、方向定义等输入时才询问这些具体缺失值；API 不支持时明确指出具体未完成设置，不以“请提供成功样例”结束工作。

遇到其他机器的 AI 询问怎样扫描 HB 时，直接读 [两频点、双方向最小配置与验收](../../docs/guides/native_hb_postprocessing.md#两频点双方向最小配置与验收)，按该机的实际项目和本机 SDK 操作，不要求用户提供另一台机器的私有工程作为前提。先读回父/子任务、参数、频率单位、实际端口激励表达式及 EM/Touchstone 块；频率参数必须被 HB 对应基频和 RF 激励引用，方向参数必须实际控制两方向激励，单纯加入扫描列表不会自动绑定端口或切换传播方向。方向取值与功率归一化由工程定义，不固定正负值。

用 `configure_hb_task` 和 `replace_parameter_sweep_sequences` 配置原生父任务；后者会删除该父任务全部已有序列，须先确认范围，且当前实现没有显式调用 `EnableSequence`。从目标工程读回序列启用状态；不要假设创建后已启用，未核实时不能声称扫描可运行。运行须有用户授权；`SimulationTask.Update()` 会执行该任务及子任务，`ParameterSweep.Start()` 是另一原生入口，不把二者或界面启动宣称为本仓库已验证等价。使用既有 `run_checked` 的真实契约，包装异常时保留原任务并检查原生日志和空闲状态，不盲目重复提交。

保存后在 schematic 结果域逐个实际谱线枚举正 Run ID 和存储参数组合，核对两个频点、两个方向所需的四种组合及所有曲线；当前别名 0、最大 ID 和回调 ID 不能替代工况身份。Post 模板应位于同一父任务内 HB 之后并实际绑定；注册资源保存重开不等于已验证回调执行。现有通用代码与示例的离线检查、项目实机运行和具体设备性能分别报告。

Update 抛异常及 post 回调的运行身份，先读[异常审计与参数绑定](../../docs/guides/circuit_update_and_result_identity.md)。
包装调用 raised 不证明 idle，不盲目保存/重跑或解除围栏；原始错误及日志保留。single_run
回调按所有必要曲线共同正 Schematic ID 和真实存储参数组合定位，不取 last/max；旧 gate
可被合法复用，但参数匹配不认证完整缓存或本轮新执行。

固定正 ID 的实际存储参数可使用[工程绑定 ByRef 查询](../../docs/guides/project_bound_run_parameter_bridge.md)。
仅在所属会话确认为空闲后做首次只读核验；不猜 Python ByRef 返回形式，不在运行中的
Post evaluate 内自动嵌套宏。文档/离线契约通过仍保持 native_bridge_verified=False。

### 自动后处理是模型交付核对项

- 手动修改 EM 参数并重跑 EM、再运行约定 HB/父任务后，绑定后处理应自动生成当前参数的完整曲线，并保留其他参数曲线供 CST 内比较；不能要求每次手动导出/刷新。HB 原始参数存储、派生曲线的参数保存及 Navigator 选择分别核对。未打通原生关联时，每参数独立 Results 也须自动生成并保存，不能覆盖同一固定叶。具体缺口、退路及双参数验收见[参数历史与自动刷新](../../docs/guides/hb_parametric_storage_and_length_results.md)。离线通过不代表自动链已验收，不修改正在扫描的工程来补证。
- 独立 Results 实现使用 `cst_solver.circuit.hb_history`：注册生成的模板后，运行约定父任务；用工程适配器核对本轮 EM、HB 正 ID 和存储参数，按完整频率/方向自动出图。托管 `run_hb_history` 沿用任务返回后的保存，单独核对 `hb_history` 回执。直接从 CST 运行需要工程适配器提供每轮执行身份，由原生工作流保存；插件安装不会绑定或部署。
- 用户要求求解后自动出图时，交付必须包含实际原生模板绑定、正确的父任务和 HB→Post 顺序、启用状态、内嵌源码与调用方设置，以及原生保存关闭重开后的绑定证据。仅有 `.rtpy`、库目录暂存、Post 空任务或静态 Results 曲线均不算完成。首次绑定、同名冲突及后续替换要分别说明；不能把“替换已绑定源码”描述成“首次注册”。
- 只配置模式不得为验收启动 EM、DC、HB、网格生成或扫描，也不得擅自执行模板。无法在当前授权范围读回绑定时，保留明确缺项，不提升验证等级或改用 Computer Use。
- 通用库只提供模板资源与调度接口；参数、频率、方向、探针、指标公式和输出分组由调用方传入。频扫横轴采用实际输入 RF；缺少方向不补零，重复执行只刷新流程拥有的曲线。有限 RF 功率同频 b/a 保留其口径，不宣称增量小信号 S。
- 首次注册优先使用所属会话 `circuit/build/register_postprocessing_template`，或所属 app 的 `circuit.register_python_result_template`。这是版本受限的 CST 2026.1 资源格式导入，每个专用 Post 只支持一个 Python 模板；首次拒绝同名，替换要求完整注册摘要。接口原生保存关闭后将该任务资源移到审计备份，重开必须从 `.cst` 重建三件套，并比对完整描述、源码、设置及任务链。不能只检查文件存在。
- `registration_persistence_verified/reopen_verified` 证明配置归档重建通过，不证明模板执行。空闲上下文原生枚举对已知有效对照也返回空，不能以空枚举判断注册失败；`binding_verified/native_template_enumeration_verified/template_execution_verified` 保持 False，不将归档持久化提升为原生模板运行认证。通用 API 不伪造 AddTemplate 命令、不运行 define/evaluate。直接调用 app facade 重开后须刷新所属会话的句柄；已注册的会话路由自动处理。
- 本版 eval_type 仅接受 single_run；不能从 RPP 的 P/EP10 推导 all_runs。资源检查返回模式 unknown（None/not_independently_decoded）及原始标志，请求声明单独记录；不得把该声明当成原生 getter。源码中明确不匹配的模式字面量会静态拒绝，不执行 define 来猜设置。
- M0D 执行后的多条 yield 输出不等于多个 Python 注册模块；检查器支持已核实的
  v11 单模块输出清单。执行改变 Summary 后，替换前重新 inspect 完整注册 SHA，
  不复用初次注册摘要。输出名清单和保存重开均不认证回调计算成功；实际重评估
  继续由调用方在授权范围内执行并核对日志、数据和表示约定。

| 需求 | 当前入口 |
|---|---|
| 离线规格检查、原理图预览 | `cst_automation.circuit_schema.validate_circuit_spec`、`cst_automation.circuit_preview.preview_circuit` |
| 静态能力发现 | `cst_solver.circuit.circuit_capabilities()`，不连接 CST |
| 配置与读回 | `app.circuit.inspect/apply/set_properties/list_pins` |
| 周期稳态射击法配置，不求解 | `app.circuit.configure_steady_state_task`；手动 value/unit 周期或自动检测，可选相对容差 |
| 常用瞬态任务配置，不求解 | `app.circuit.configure_transient_task`；`create=True` 仅创建新名称 |
| 端口激励、内阻、终端阻抗 | `app.circuit.configure_task_ports`，Sine/Import；实际 ExternalPort 名称 |
| 内置二极管/SPICE 模型 | `app.circuit.configure_nonlinear_model`，默认只更新；不自动连线 |
| CST Python 后处理模板 | `app.circuit.register_python_result_template`；MCP `register_circuit_postprocessing_template`。仅暂存时使用 `stage_python_result_template` |
| 当前三维工程的稳定因子/时间信号采样 | `app.configure_em_time_settings`，独立于 DS task |
| 三维连接 | `app.circuit.link_em` |
| 依赖检查与副本收集 | `inspect_dependencies/bundle` |
| 通用参数研究 | `app.circuit.run_parameter_study`；MCP `run_circuit_parameter_study` |
| 指定任务运行 | `app.circuit.run_checked` |
| 电路结果读取 | `CircuitResult.get_tree_items/get_run_ids/read_curve/export_csv` |
| 串行服务 | `tpc_service.circuit.register_circuit_handlers` |
| MCP | `cst_mcp.circuit_tools.register_circuit_tools` 或 `--enable-circuit` |

调用签名以源码和公共协议为准。不要把验证脚本中的原生 SDK 操作当成已有高层 API。

## 通用参数研究与历史比较

拓扑不变的纯电路或同工程 EM＋电路参数研究，先检查 CST Design Studio 原生 Parameter Sweep 及任务链是否满足参数、依赖和输出要求；满足时优先原生扫参，避免逐点 Python 写入和求解的通信时延。需要逐点决策、特定证据归档或原生任务无法满足的明确需求时，使用 `app.circuit.run_parameter_study(spec)`；结构和用法见 [通用参数研究](../../docs/guides/circuit_parameter_studies.md)。这是会保存和求解的显式逐点序列，不是原生扫描配置接口。参数 scope、单位、元件绑定、已有叶任务和结果路径必须明确；全局参数使用调用者核对的原生单位，已固化元件值用 block/property 显式更新。

- 每点使用匹配的 EM 数据；指定 EM 数据文件必须更新、原生状态 SUCCESS 且结果全局参数匹配。仅日志/全目录变化不能放行；缺原生来源证据返回 unverified。第一版 EM 依赖每点重算，不宣称自动缓存复用、外部 EM 映射或瞬态双向联合已支持。
- 保留每批次/每工况的复数原始数据、单位、参数读回、EM 来源及电路运行证据。汇总叶按批次和工况唯一命名，不用 replace=True 覆盖其他参数的曲线，不把当前 run 0 当成不可变历史。
- 结果量由调用方提供，不在通用 study 中加入隔离器指标、固定端口/频段/二极管数。领域分析继续用各自后处理流程。
- 通过 StudyResult 过滤和比较；交付给出实际归档和 CST Results/Studies 入口。保存读回与原生关闭重开分别记录；未经重开检查，不承诺单个 .cst 已封装全部历史文件。离线测试通过不能写成 EM/HB 或工程重开已验收。

## 配置和连接

1. 从目标工程实际读回元件、引脚、任务、单位和依赖。先明确是 `network` 还是 `transient_cosim`；普通电路瞬态不等于三维双向联合。
2. 使用 schema v1：`units/parameters/blocks/external_ports/nets/probes/em_links/tasks`。元件使用实际官方类型及 `property_units`；net 端点包含 `component_kind/component_name/pin_name`。不得猜测 pin 索引。
3. 使用 `preview_circuit(spec, destination)` 输出离线原理图。涉及三维几何或端口改变时，以真实坐标提供预览，经审阅后再建模；已批准的范围不重复询问。
4. `apply` 仅支持 `conflict="error"`，遇到重名不删除旧对象。部分写入失败要保留副本、消息及读回，不盲目重试整个配置。
   可以先创建元件/端口，再仅提交 nets、探针或任务；引用按当前工程读回校验，
   不重复声明已有元件。连接使用 `list_pins` 的实际 `pin_name`，界面带标签名称
   保留在 `display_pin_name`；不猜测或混用 pin_index、port_index。
5. 同工程已有 EM 块用 `source="self"` 引用，不重复创建。`port_map` 每项必须显式包含 `pin_name/port_id/mode/reference/polarity`；`parameter_map` 显式传入。`verified=False` 保留原义。
6. 参数表达式目前求值后固化为元件值。修改工程全局参数不会自动刷新该值；通过 `set_properties(..., units=...)` 明确更新，再保存。不要声称当前参数序列是原生 DS 扫描。

## 工程中运行和读取

### HB 放行、代表工况与失败停止

HB 或其父扫描运行前，执行 [HB 数据覆盖与停止门槛](references/hb-and-postprocessing.md#hb-运行前的放行门槛)：逐一核对实际被动块/链接文件的 DC 与全部保留混频范围；全局 `fmin=0` 不构成覆盖证据。参考 NPORT 与新链接 EM 分别验收；拓扑或 EM 数据改变后，先完成有界正反向代表工况的 DC 工作点、实际 RF 入射/匹配和谱线检查，再放行完整父扫描。

首个初始化或数值失败后停止后续参数组；没有本轮有效上游输入的同级后处理应跳过，报告上游首要错误，避免缺节点报错级联。此门槛由调用方编排执行，不能从配置接口、HB→Post 顺序或通用 `run_checked` 名称推断已自动实现；原生 sequence 的 `Abort if subtask fails` 只在对应任务类型与版本设置已核对时使用。

### HB 任务的 CPU 并行度

- CST Design Studio 的 Spectral Lines/HB 在 `Properties > Specials > General > Parallelization` 设置 CPU 并行度。运行前核对目标 HB 任务本身；不要从电脑显示的逻辑线程数推断任务当前并行度。
- 没有用户指定的线程上限时，优先使用 CST 的 `Maximum`，让 CST 按当前可用的物理核心数选择并行度。确需限额时使用 `Use up to`，依据 CST/操作系统实际识别的核心数指定；混合架构 CPU 的产品规格不等于当前运行环境暴露给 CST 的核心数。
- 创建或更新 HB 任务的自动化不得无依据地写死线程数（例如 8）。若设置接口的枚举值尚未在当前 CST 版本验证，不猜测字符串；使用已核实的原生设置入口。
- 求解后从本轮原生日志确认实际线程数，并记录所选并行模式与线程数。日志里的线程数证明本轮实际使用量，不代表电脑的硬件上限；“忽略超线程”也不等于禁用了物理核心并行。
- Design Studio 电路 HB 的 CPU 并行度与三维电磁求解器 GPU 加速是不同设置；不要用 EM 的 GPU 状态推断 HB 是否并行。

用户实际开展工程并要求求解时：

- 在已保存的工作副本上执行明确任务，使用 `run_checked(task_name, mode=..., expected_results=..., reuse="never")`。每个预期结果包含真实 `tree_path` 和整数 `run_id`，从读回取得，不假定 run 0 永远代表本轮。
- `transient_cosim` 要求实际 transient 任务的 `circuit simulator` 为 `cosimulation`，由运行契约检查目标任务和三维侧证据。不要改用裸 `Update` 绕过失败。
- 普通 DS 网络瞬态与 EM→HB 工作流不同；未绑定工作流的会话可使用 `circuit/solve/run_network_transient`，显式传 `task_name` 和 `expected_results`。运行前原生核对 transient、cst 网络模式和无子任务；已绑定工作流或存在保护标记的工程拒绝独立入口。该入口尚不支持强制 MOR 复用或原生取消；不能满足用户要求时不提交。不把 `mode=network` 当作纯瞬态证明，也不改用裸 SDK 绕过保护。
- `reuse='verified'` 是既有结果缓存契约，不是要求复用 MOR；当前无法证实时不得声称 MOR 命中，要求必须复用而无法在启动前可靠保证时，不提交可能冷启动的求解。MOR 文件存在、修改时间或单次耗时均不足以证明复用。
- 用户要求 120 秒等可取消截止时，先确认独立控制路径能针对所属任务发出原生取消并读回停止状态；当前库未证实该能力时明确报告未实现，不把 Python 等待超时、线程中断或强杀进程当作 CST 停机。
- 文件引用先用 `inspect_dependencies` 核对实际路径及摘要；缺失、迁移或原生更新不可验证时报告具体依赖及状态，不借 Update File References 对话框冒充 API 完成。
- 读取电路结果用 `CircuitResult` 的 schematic 域，先列树路径与 run ID，再读取/导出。保留单位、参数、摘要、工程路径；幅值约定、电流方向或 FFT 窗口未知时保持 unknown。
- 常用瞬态设置优先使用 `configure_transient_task(task_name, settings, create=False)`，显式指定 mode、带 value/unit 的 duration；sampling、integration、max_frequency、accuracy 按指南提供。接口转换到已有工程单位，先设置区间、最后选采样方式；不自动求解。
- integration 支持 stepping=automatic/adaptive/fixed、method=adams/gear、整数 order=1..4。adaptive 的 minimum_time_step 不得超过 time_step，automatic 不接收显式步长。普通网络瞬态显式算法建议同时设 auto_solver=False；真实联合的算法和时钟仍须运行证据，不用 DS 请求选项取代 EM 时间控制。
- 端口源优先用 `configure_task_ports`。voltage/current 配置带单位 Sine，或两列 SI 秒与 V/A 的 CSV Import；periodic 为布尔值。Voltage 的 resistance 与 none 终端的 impedance 不混用；none 会清除旧激励。当前不封装电流源内电导。信号完整参数/终端阻抗读回标记 unsupported，文件摘要仅代表配置时快照。
- 模型优先用 `configure_nonlinear_model`。kind=berkeley_diode 的 parameters 接受 IS/N/RS/CJO/TT/BV/IBV/VJ/M/XTI/AREA；物理量显式 value/unit，其他为无量纲数值。新建时先选模型、再写参数；已有兼容模型只改提供的项，不再次选择 Model Type 重置未指定值。create=True 拒绝重名，默认拒绝缺失或不兼容块。
- kind=spice 使用调用方提供的 file/model，可选 dialect=AUTOMATIC/SPICE3/PSPICE/HSPICE；不生成模型、不猜引脚、不自动接线。检查返回的 pins_before/pins_after；换模型后需重查原连接。service 输入文件在 workdir 内，相对路径按 workdir 解析。
- EM 时间控制使用 `app.configure_em_time_settings({"stability_factor": 0.5, "output_sampling": "every_step"})`。因子为 `(0,1]` 内的有限数字，输出采样可选 every_step/automatic；非空稀疏字典只修改提供的字段。作用域仅当前工程 model3d，不改变 DS 采样或外部链接，不 Reset/重建/求解；Python 调用后显式保存。
- 输出采样间隔不能证明内部积分步长。`Simulated` 的 points 不代表实际点数；EM 因子也不是绝对 ps。两种配置接口均保留 `internal_time_step_verified=False`。EM 接口无可靠 getter，`readback=None/readback_status="unsupported"`，不把历史提交当作原生设置读回或每步输出证明。此组合封装本轮只有离线验证；未来工程从实际日志/原始点核验。
- EM 历史提交失败可能部分写入，保留错误中的 requested/native_commands 和阶段，不重试整段或自动回滚；service 会保存部分工程及失败审计。缺少 model3d 不回退到 schematic。
- 内置二极管的模型身份可来自明确标注的原生参数模式证据，不能把请求枚举当作原生 getter。SPICE 选中模型名、方言和源文件摘要分别保留；若求解后模型名变化（包括出现前缀），不要自行删除前缀或忽略配置差异。
- 修改现代六面体网格时核对实际生成网格；部分旧 Mesh 命令在新生成器中无效。需要校准命令时参考本机官方 MeshSettings 示例，不凭下发命令即声称加密。
- `unverified` 不等于已成功；服务将其映射为 failed / `circuit_result_unverified`。保留原审计和产物，再按当次工程需要补证。
- 若 SDK 停滞，转用 `cst-diagnostics`，读取实际弹窗标题、正文、按钮及进程归属；超时或窗口消失不证明成功。

### HB 与瞬态结果对照

- 先说明两种结果回答的问题不同：HB 按输入频率逐点扫描，可形成频率响应；单频瞬态给出该输入频率下的时域响应。对单频瞬态做 FFT 得到的谐波或混频边带，不是其他输入频率的扫频点，也不能拼成 HB 式频响曲线。
- 计划瞬态频扫时，明确频点数、传播方向和偏置/泵浦状态；按“频点数 × 方向数 × 状态数”估算运行次数，并用已观察到的单次耗时估算总时间。若瞬态只覆盖中心频率，应将其标为单点交叉核验，不暗示覆盖整段频带。
- 声称 HB 与瞬态一致前，必须有可审阅的同工况对照表或图；在图表或其说明中注明两侧实际结果树路径/run ID、共同观测量、归一化方式、提取时间窗、差值及判定门槛。没有事先约定且有依据的门槛时只报告数值差，不给通过/一致结论。HB 全频扫描加一个瞬态频点至多支持该匹配频点的比较，不能外推为整段瞬态验证。若尚无直接对照产物，明确写“尚未建立直接对照”。
- 只有在输入频率、方向、偏置/泵浦、端口和负载、可用入射功率或电压、器件状态及归一化定义一致时，才把两种方法作数值对照。瞬态提取量若不满足 S 参数的功率波定义与归一化，就标为输出基波或端口响应，不称作 S21。
- 报告中直接叠画 HB 频率曲线与实际完成的瞬态频点；在共同频点并列幅值和相位，并另画差值及预先声明的判定门槛。保留两侧复数原值、单位、工况和数据来源。相位差用圆周差 `arg(S_TR / S_HB)`，幅值差用 `20 log10(|S_TR| / |S_HB|)`；避免对已包裹的相位角直接相减。
- 瞬态结果用于基波对照时，记录舍弃渐启后的分析时间窗、稳态周期检查、FFT/拟合方法及时间步证据；HB 则记录收敛状态和谐波设置。若差值超限，只能先报告两种提取结果不一致；继续核对端口归一化、源与器件端电压、偏置状态、时间窗、步长和 HB 收敛，不能仅凭差值断定某一种方法正确。

## 二极管评估：电压曲线为必需交付

用户的长期要求：以后评估二极管时，必须与 S 参数、性能指标和结论一并画出实际二极管电压曲线，不再等用户单独提醒。单管、偏置检查和多管阵列均适用；当次用户明确缩小范围时遵从当次指令。

- 每只被评估二极管都提供实际 A−K 总电压随时间曲线，包含实际 DC 与交流分量；标明 A/K 极性、时间/电压单位、RF/泵浦频率与功率、偏置及数据来源。多方向或多工况评估应在一致条件下叠图或分面比较，不能只输出一个峰值或用源设置电压替代器件端电压。
- 涉及 RF/泵浦调制时，同时提供实际 DC、泵频和 RF 同频分量的峰值与相位；多管阵列沿器件位置分别展开相位，保留共同源时钟参考。区分波形总峰值与分量峰值，核对原生零频谱线与波形的 DC 约定。
- 自动后处理须同步生成电压图及可追溯原始数据；CST 内的自动图表同时包含原生 Results 电压节点，核对保存读回。报告给出实际绘制的图和数据入口，不以“已有探针/已有数据/将来可画”替代交付。优先使用代码和已有结果，不为补图自行增加授权之外的求解。
- 验收时将“各管电压曲线已绘制并与来源核对”作为必查项；不能仅凭 S 参数图或标量表宣布二极管评估交付完整。缺数据时在当次授权范围内补齐；无法补齐则明确列为缺项，不编造曲线。

## 服务和扩展开发

所有 CST 访问经同一服务 worker；显式注册，不改全局 MCP 配置。服务 `params.workflow="circuit"` 的现有路由为：

| kind | operation |
|---|---|
| `build` | `configure`、`configure_transient_task`、`configure_steady_state_task`、`configure_task_ports`、`configure_nonlinear_model`、`stage_postprocessing_template`、`register_postprocessing_template`、`configure_em_time_settings`、`inspect`、`read_results`、`package` |
| `solve` | `run_task` |
| `study` | `parameter_sequence`、`run_parameter_study` |

MCP 工具（含新增通用参数研究入口）为 `preview_circuit/inspect_circuit/configure_circuit/configure_circuit_transient_task/configure_circuit_steady_state_task/configure_circuit_task_ports/configure_circuit_nonlinear_model/stage_circuit_postprocessing_template/register_circuit_postprocessing_template/configure_em_time_settings/run_circuit_task/read_circuit_results/package_circuit_project/run_circuit_parameter_study`。端口工具使用 task_name/ports，模型工具使用 block_name/settings/create；均只配置保存。`stage` 后处理工具只静态检查并暂存库文件，不修改工程；要求实际内嵌注册时用 `register`，遵守上面的版本、单模板与归档读回合同。EM 时间工具使用 settings 与工程标识，不需 task_name。参数序列尚不是独立 MCP 工具，不自行假定已暴露。所有工程和导出路径位于服务 workdir 内。

新增功能优先沉淀到通用 Python 接口，再接 service/MCP；跨包协议先更新 `PUBLIC_API.md`。共享数据放 `cst_automation`，SDK 在执行时惰性加载，不引入 TPC 或 em-enclosure 依赖。

`bundle` 当前只是依赖清点和复制，不保证 CST 二进制链接重定位；保留 `portable_verified=False`。SPICE `.lib`、外部 CST 闭包、缓存复用和中断恢复按实际实现标注边界。

交付时分别报告：本轮新增功能、可调用入口、离线检查、原理图/几何读回、实际求解和数值证据；未运行项写“未执行”，不补做无关验收来填满清单。


### 周期稳态 shooting

- `configure_steady_state_task(task_name, settings, create=False)` 将明确的 transient
  任务切到 `cst - steady state`，只配置，不保存或求解。settings 支持
  automatic_period、带 value/unit 的 period、可选 (0,1) 相对 tolerance；提供 period
  默认手动，否则默认自动，冲突输入在 SDK 前拒绝。省略容差不改已有值。
- 先配置普通瞬态积分设置与端口，再启用 shooting；后续调用 configure_transient_task
  会按显式模式切换求解器。周期按实际任务时间单位换算，含局部单位。
- 不修改源/DUT/采样/积分设置。周期激励的相容性、实际求解残差、时域向量拟合、
  被动性、长延迟敏感性与谱归一化仍需独立验证。当前只离线测试，不保证加速。
- 该能力是瞬态射击法；不把它描述成 Circuit Envelope 或泵浦 HB 小信号接口。
