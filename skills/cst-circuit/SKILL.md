---
name: cst-circuit
description: Use when developing or using CST Design Studio circuit schematics, EM port links, network or transient field-circuit co-simulation, circuit results, or their service and MCP interfaces in cst-automation.
---

# CST 场路联合

使用本仓库的 `app.circuit` 与 `CircuitResult`，区分原理图配置、网络协同计算和瞬态场路联合。仅在三维模型中放置集总元件的任务使用 `cst-modeling` / `cst-simulation`。

先读 [使用指南](../../docs/guides/circuit_cosimulation.md)。开发接口时再读 [公共协议](../../docs/PUBLIC_API.md)；确认实机能力时读 [验证记录](../../docs/VALIDATION.md)，不要从接口存在推断验收通过。

## 当前工作重点

当前以功能完善和可复用工作流为主，见 [开发重点](../../docs/CIRCUIT_DEVELOPMENT.md)。不为了补齐验收矩阵自行启动样例、非线性求解、网格或时间步收敛扫描。后续实际工程中围绕当次目标逐步验证；保留既有门槛和未验证项。修改程序所必需的小范围离线检查可以开展，不把全套实机验收设为每项功能开发的前置条件。

## 选择入口

| 需求 | 当前入口 |
|---|---|
| 离线规格检查、原理图预览 | `validate_circuit_spec`、`preview_circuit`，位于 `cst_automation` |
| 静态能力发现 | `cst_solver.circuit.circuit_capabilities()`，不连接 CST |
| 配置与读回 | `app.circuit.inspect/apply/set_properties/list_pins` |
| 常用瞬态任务配置，不求解 | `app.circuit.configure_transient_task`；`create=True` 仅创建新名称 |
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
- 输出采样间隔不能证明内部积分步长。`Simulated` 的 points 不代表实际点数；配置接口始终返回 `internal_time_step_verified=False`。三维稳定因子和每步输出控制仍按当前源码/本机帮助确定调用，不虚构已封装的高层 EM 时钟接口。
- 内置二极管的模型身份可来自明确标注的原生参数模式证据，不能把请求枚举当作原生 getter。SPICE 选中模型名、方言和源文件摘要分别保留；若求解后模型名变化（包括出现前缀），不要自行删除前缀或忽略配置差异。
- 修改现代六面体网格时核对实际生成网格；部分旧 Mesh 命令在新生成器中无效。需要校准命令时参考本机官方 MeshSettings 示例，不凭下发命令即声称加密。
- `unverified` 不等于已成功；服务将其映射为 failed / `circuit_result_unverified`。保留原审计和产物，再按当次工程需要补证。
- 若 SDK 停滞，转用 `cst-diagnostics`，读取实际弹窗标题、正文、按钮及进程归属；超时或窗口消失不证明成功。

## 服务和扩展开发

所有 CST 访问经同一服务 worker；显式注册，不改全局 MCP 配置。服务 `params.workflow="circuit"` 的现有路由为：

| kind | operation |
|---|---|
| `build` | `configure`、`configure_transient_task`、`inspect`、`read_results`、`package` |
| `solve` | `run_task` |
| `study` | `parameter_sequence` |

MCP 当前七个工具为 `preview_circuit/inspect_circuit/configure_circuit/configure_circuit_transient_task/run_circuit_task/read_circuit_results/package_circuit_project`。参数序列尚不是独立 MCP 工具，不自行假定已暴露。所有工程和导出路径位于服务 workdir 内。

新增功能优先沉淀到通用 Python 接口，再接 service/MCP；跨包协议先更新 `PUBLIC_API.md`。共享数据放 `cst_automation`，SDK 在执行时惰性加载，不引入 TPC 或 em-enclosure 依赖。

`bundle` 当前只是依赖清点和复制，不保证 CST 二进制链接重定位；保留 `portable_verified=False`。SPICE `.lib`、外部 CST 闭包、缓存复用和中断恢复按实际实现标注边界。

交付时分别报告：本轮新增功能、可调用入口、离线检查、原理图/几何读回、实际求解和数值证据；未运行项写“未执行”，不补做无关验收来填满清单。
