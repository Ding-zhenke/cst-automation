---
name: cst-circuit
description: Use when developing or using CST Design Studio circuit schematics, EM port links, network or transient field-circuit co-simulation, circuit results, or their service and MCP interfaces in cst-automation.
---

# CST 场路联合

实际 Codex 操作先使用[对话持久会话](../cst-sessions/SKILL.md)，配置/求解/在线读回均借用同一会话。

使用本仓库的 `app.circuit` 与 `CircuitResult`，区分原理图配置、网络协同计算和瞬态场路联合。仅在三维模型中放置集总元件的任务使用 `cst-modeling` / `cst-simulation`。

先读 [使用指南](../../docs/guides/circuit_cosimulation.md)。开发接口时再读 [公共协议](../../docs/PUBLIC_API.md)；确认实机能力时读 [验证记录](../../docs/VALIDATION.md)，不要从接口存在推断验收通过。

## 当前工作重点

实际工程的几何尺寸、材料与二极管参数、频段、偏置、泵浦及扫描范围属于用户私有产物，
不得从工程中提炼到通用 skill 或示例；可复用流程只保留接口、符号参数和证据要求。

当前以功能完善和可复用工作流为主，见 [开发重点](../../docs/CIRCUIT_DEVELOPMENT.md)。不为了补齐验收矩阵自行启动样例、非线性求解、网格或时间步收敛扫描。后续实际工程中围绕当次目标逐步验证；保留既有门槛和未验证项。修改程序所必需的小范围离线检查可以开展，不把全套实机验收设为每项功能开发的前置条件。

## 选择入口

代码优先：配置/读回用原生 Python/API，必要时使用有依据的 VBA；日志、数据和
API 可完成的检查不走 computer use。只有缺少接口、需要处理实际对话框或核对
实际显示时才集中使用界面操作，避免反复截图和轮询。

HB 基频/阶数、原生 Parameter Sweep 序列、指定运行的谱线、Results 曲线写入，
以及已绑定模板源码替换，使用 [原生 HB 与后处理接口](../../docs/guides/native_hb_postprocessing.md)。
这些接口不自动求解/保存；模板资源更新后仍需原生保存重开核验，不代表支持首次自动绑定。

| 需求 | 当前入口 |
|---|---|
| 离线规格检查、原理图预览 | `validate_circuit_spec`、`preview_circuit`，位于 `cst_automation` |
| 静态能力发现 | `cst_solver.circuit.circuit_capabilities()`，不连接 CST |
| 配置与读回 | `app.circuit.inspect/apply/set_properties/list_pins` |
| 常用瞬态任务配置，不求解 | `app.circuit.configure_transient_task`；`create=True` 仅创建新名称 |
| 端口激励、内阻、终端阻抗 | `app.circuit.configure_task_ports`，Sine/Import；实际 ExternalPort 名称 |
| 内置二极管/SPICE 模型 | `app.circuit.configure_nonlinear_model`，默认只更新；不自动连线 |
| CST Python 后处理模板 | `cst_automation.result_templates.stage_python_result_template`；MCP `stage_circuit_postprocessing_template` |
| 当前三维工程的稳定因子/时间信号采样 | `app.configure_em_time_settings`，独立于 DS task |
| 三维连接 | `app.circuit.link_em` |
| 依赖检查与副本收集 | `inspect_dependencies/bundle` |
| 指定任务运行 | `app.circuit.run_checked` |
| 电路结果读取 | `CircuitResult.get_tree_items/get_run_ids/read_curve/export_csv` |
| 串行服务 | `tpc_service.circuit.register_circuit_handlers` |
| MCP | `cst_mcp.circuit_tools.register_circuit_tools` 或 `--enable-circuit` |

调用签名以源码和公共协议为准。不要把验证脚本中的原生 SDK 操作当成已有高层 API。

## 配置和连接

1. 从目标工程实际读回元件、引脚、任务、单位和依赖。先明确是 `network` 还是 `transient_cosim`；普通电路瞬态不等于三维双向联合。
2. 使用 schema v1：`units/parameters/blocks/external_ports/nets/probes/em_links/tasks`。元件使用实际官方类型及 `property_units`；net 端点包含 `component_kind/component_name/pin_name`。不得猜测 pin 索引。
3. 使用 `preview_circuit(spec, destination)` 输出离线原理图。涉及三维几何或端口改变时，以真实坐标提供预览，经审阅后再建模；已批准的范围不重复询问。
4. `apply` 仅支持 `conflict="error"`，遇到重名不删除旧对象。部分写入失败要保留副本、消息及读回，不盲目重试整个配置。
5. 同工程已有 EM 块用 `source="self"` 引用，不重复创建。`port_map` 每项必须显式包含 `pin_name/port_id/mode/reference/polarity`；`parameter_map` 显式传入。`verified=False` 保留原义。
6. 参数表达式目前求值后固化为元件值。修改工程全局参数不会自动刷新该值；通过 `set_properties(..., units=...)` 明确更新，再保存。不要声称当前参数序列是原生 DS 扫描。

## 工程中运行和读取

用户实际开展工程并要求求解时：

- 在已保存的工作副本上执行明确任务，使用 `run_checked(task_name, mode=..., expected_results=..., reuse="never")`。每个预期结果包含真实 `tree_path` 和整数 `run_id`，从读回取得，不假定 run 0 永远代表本轮。
- `transient_cosim` 要求实际 transient 任务的 `circuit simulator` 为 `cosimulation`，由运行契约检查目标任务和三维侧证据。不要改用裸 `Update` 绕过失败。
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
| `build` | `configure`、`configure_transient_task`、`configure_task_ports`、`configure_nonlinear_model`、`stage_postprocessing_template`、`configure_em_time_settings`、`inspect`、`read_results`、`package` |
| `solve` | `run_task` |
| `study` | `parameter_sequence` |

MCP 当前十一个工具为 `preview_circuit/inspect_circuit/configure_circuit/configure_circuit_transient_task/configure_circuit_task_ports/configure_circuit_nonlinear_model/stage_circuit_postprocessing_template/configure_em_time_settings/run_circuit_task/read_circuit_results/package_circuit_project`。端口工具使用 task_name/ports，模型工具使用 block_name/settings/create；均只配置保存。后处理模板工具只静态检查并暂存 `.rtpy` 文件，不打开或修改 CST 工程；用户需将返回的 library_root 加入 CST 库路径，并在 Post-Processing 任务的模板对话框中添加模板一次。此后 CST 可在对应求解后自动执行。EM 时间工具使用 settings 与工程标识，不需 task_name。参数序列尚不是独立 MCP 工具，不自行假定已暴露。所有工程和导出路径位于服务 workdir 内。

新增功能优先沉淀到通用 Python 接口，再接 service/MCP；跨包协议先更新 `PUBLIC_API.md`。共享数据放 `cst_automation`，SDK 在执行时惰性加载，不引入 TPC 或 em-enclosure 依赖。

`bundle` 当前只是依赖清点和复制，不保证 CST 二进制链接重定位；保留 `portable_verified=False`。SPICE `.lib`、外部 CST 闭包、缓存复用和中断恢复按实际实现标注边界。

交付时分别报告：本轮新增功能、可调用入口、离线检查、原理图/几何读回、实际求解和数值证据；未运行项写“未执行”，不补做无关验收来填满清单。
