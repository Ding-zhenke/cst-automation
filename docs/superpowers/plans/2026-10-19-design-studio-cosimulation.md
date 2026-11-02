# Design Studio 场路联合仿真实施计划（待审阅）

> 当前优先级更新（2026-10-19）：按用户最新安排，先完善功能和 skill，后续实际工程中逐步验证。本文早期阶段顺序及待审阅文字保留历史含义；当前执行范围见 [开发重点](../../CIRCUIT_DEVELOPMENT.md)，实际进展以 [验证记录](../../VALIDATION.md) 为准，不再以完成专项验收矩阵作为继续功能开发的前置条件。

2026-10-19 更新：用户已批准接口与离线阶段。当前交付为 `0.2.0.dev0`；V1–V7 实机验证及三维建模/求解仍待预览审阅。下方原始清单保留总体目标，不因离线通过而勾选实机步骤。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the main session. Steps use checkbox (`- [ ]`) syntax for tracking.

执行方式建议：主会话按阶段串行实施。本文件是用户要求的待审阅方案，不授权当前开始编码、建模或求解。

**Goal:** 为通用 `cst-automation` 增加三维电磁结构与 Design Studio 电路的配置、连接、任务执行、结果读取及实机验收能力。

**Architecture:** 官方 Python 原理图对象优先，SDK 缺口使用受限原理图 VBA 适配。新增 `setup.circuit` 和独立电路结果读取器；服务任务保持单 worker，MCP 显式注册并通过服务执行。先同工程连接，再外部链接；`network` 与 `transient_cosim` 分别验收。

**Tech Stack:** 本仓库 Python `.venv`、NumPy、pytest、可选 MCP SDK、本机 CST Studio Suite 2026 SDK；SVG 预览使用标准库输出，不新增必需运行依赖。

**Spec:** [设计、拟定接口与实机验收规格](../specs/2026-10-19-design-studio-cosimulation-design.md)。所有数值、单位、运行模式和容差以该规格为准；两份文件一起审阅。

## Global Constraints

- 不依赖或 import `mesh_grid`、`topo_modeler`、`topo_templates`、`tpc_toolkit`、`em_enclosure`。
- 保留 `cst_solver`、`tpc_service`、`cst_mcp`；共享数据/schema 放 `cst_automation`。
- 普通导入不连接 CST、不加载 CST DLL；`cst` 不作为 PyPI 依赖。
- 变更跨包协议前先更新 `docs/PUBLIC_API.md`，保持 handler 和 MCP 扩展显式注册。
- 用户先审阅本方案；实施中的真实几何/端口预览还须在建模前审阅。
- 所有工程、备份、临时文件与实机结果放本仓库 `work/`；源 TPC、CST 安装和用户工程只读。
- 不修改相邻仓库、全局 MCP 配置、公共 Python 环境；不覆盖同时发生的无关修改。
- 不更改现有 `setup.run()`、`setup.run_checked()`、`Result(path)` 默认行为。
- 不混淆 offline、原理图/几何读回、solver、数值验证；未通过者不得抬高验证等级。
- 不在本规划回合提交或推送。后续本地提交由主会话统一管理推送。

## Review Focus

1. pin 名、pin 索引、三维 port ID 与 mode 混用：必须根据各对象实际读回转换，并拒绝模糊映射。
2. RLC 局部单位与参数表达式：必须保持量纲、作用域和写入后的值，不能把 pF 当 F。
3. 同一个 `.cst` 内其他任务完成、旧数据或缓存命中：不得误判为目标任务本次求解成功。
4. 外部 CST/SPICE/Touchstone 链接及工作副本移动：必须解析并重定位已支持的依赖；缺失明确失败。
5. 阻塞 SDK、结果删除提示、借用会话：保持唯一 worker、保留失败证据、不误关用户工程。

## 文件与职责

以下均为拟新增/拟修改，当前仅创建本规划与设计文档。

| 文件 | 职责 |
|---|---|
| `cst_automation/circuit_schema.py` | 版本化规格、单位/端点/参数校验 |
| `cst_automation/circuit_preview.py` | 离线 SVG、连接表、参数摘要 |
| `cst_solver/circuit/__init__.py`、`api.py` | `CircuitAPI` facade，惰性绑定与明确错误 |
| `cst_solver/circuit/capabilities.py`、`adapter.py` | SDK/CST 2026 能力探测、受限原生命令/VBA适配 |
| `cst_solver/circuit/blocks.py`、`nets.py` | 元件、端口、探针、连接及结构化读回 |
| `cst_solver/circuit/tasks.py` | 任务、激励、参数设置和模式预检 |
| `cst_solver/circuit/links.py` | 三维链接、端口映射、依赖枚举/复制/重定位 |
| `cst_solver/circuit/run.py` | 任务级运行契约、缓存和证据记录 |
| `cst_solver/circuit/results.py` | `CircuitResult`，保存后的电路结果读取/导出 |
| `cst_solver/__init__.py`、`project.py`、`setup.pyi` | 新 facade/DS 工程入口和类型声明 |
| `tpc_service/circuit.py`、`backends/base.py` | 显式 handler 路由及失败证据兼容扩展 |
| `cst_mcp/circuit_tools.py`、`runtime.py`、`tools.py` | 显式工具注册、能力报告、服务路由 |
| `tests/test_circuit_schema.py`、`test_circuit_preview.py` | 离线数据与预览测试 |
| `cst_solver/tests/test_circuit_*.py` | SDK stub、读回、运行归属与结果测试 |
| `tpc_service/tests/test_circuit_service.py` | worker/handler/状态与失败产物测试 |
| `cst_mcp/tests/test_circuit_tools.py` | schema、注册、读写标注和任务路由 |
| `tests/live/test_circuit_validation.py`、`tests/live/README.md` | 显式开启的分阶段实机脚本与运行说明 |
| `docs/PUBLIC_API.md`、`VALIDATION.md`、`guides/circuit_cosimulation.md`、`README.md` | 公共接口、证据边界、使用方式 |
| `pyproject.toml` | 实机测试标记、必要 package-data、最终版本 |

新增目录中的类型声明与 package-data 同步配置；不依赖未打包的工作目录文件。实施遇到既有文件并发修改，先重新读当前内容再做最小变更。

## Task 1：协议草案、离线规格与预览

**Consumes:** 设计文档 §4.1 的 `CircuitSpec`；不使用 CST。

**Produces:** `validate_circuit_spec(spec: dict) -> dict`；`preview_circuit(spec: dict, output_dir: str) -> dict`。

- [ ] 先更新公共协议草案，标记拟新增能力、字段、错误码和兼容边界。
- [ ] 添加失败用例：`test_reject_duplicate_names`、`test_reject_unknown_endpoint`、`test_units_preserve_pf_expression`、`test_reject_cross_domain_parameter_collision`、`test_preview_does_not_load_cst`。
- [ ] 运行上述测试，确认失败来自缺少目标能力；实现最小 schema/预览并重跑。
- [ ] 用 RLC 规格断言 SVG、连接表、参数表与源摘要一致；不测试无关像素细节。
- [ ] 只对该任务相关文件建立本地提交，记录离线证据。

## Task 2：CST 能力确认、DS 会话与原理图读写

**Consumes:** Task 1 已校验规格。

**Produces:** `setup.new_circuit_project()`；静态 `circuit_capabilities()`；`app.circuit.capabilities/inspect/list_block_types/list_pins/apply/set_properties/validate`，签名见设计 §4.2。

- [ ] 添加失败用例：`test_lazy_circuit_property`、`test_schematic_none_is_explicit`、`test_reset_before_each_block`、`test_pin_name_resolution_uses_actual_index`、`test_conflict_does_not_delete_existing_block`、`test_property_units_readback`。
- [ ] 运行失败测试；实现官方对象优先的 adapter 和 RLC/端口/接地/探针/网络操作，再跑测试。
- [ ] 以只读/微型工作副本检查本机 SDK 对象、属性、返回值；记录可用与 unknown，许可证是否可用必须单独记录。
- [ ] 完成 V1：独立 DS 工程写入→读回→显式保存→关闭→重开读回；保存完整连接/单位/探针方向证据。
- [ ] 未通过 V1 不进入后续真实求解；通过后本地提交，仍只声明读回通过。

## Task 3：指定任务、运行契约和电路结果

**Consumes:** 可读回的原理图、TaskSpec 和 expected_results。

**Produces:** `app.circuit.run_checked(...)`；`CircuitResult(path)` 的五个结果方法，签名见设计 §4.4–4.5。

- [ ] 添加失败用例：`test_update_selected_task_only`、`test_wrong_mode_rejected_before_submit`、`test_other_task_result_does_not_prove_success`、`test_run_id_domain_is_explicit`、`test_constant_recomputed_data_can_succeed`、`test_missing_expected_curve_is_unverified`、`test_saved_schematic_results_selected`。
- [ ] 运行失败测试；实现任务/激励配置、指定任务 Update、保存、目标身份和必需结果检查；不重写现有三维 run contract。
- [ ] 验证失败时日志、消息、任务身份和已产生的文件可保留；单位未知和数据解码失败不静默替代。
- [ ] 完成 V2：301 点 RLC 解析 S 参数对照、纯电路瞬态独立方程对照、UI/API 独立副本比较、C=1→2→1 pF。
- [ ] 记录实际树路径与 run ID、参数组合、误差和缓存行为，按冻结容差判定；本地提交。

## Task 4：同工程电磁链接与两种联合模式

**Consumes:** Task 2 的实际 pin 读回、Task 3 的运行与结果契约。

**Produces:** `app.circuit.link_em(...)` 的 self 分支；`network/transient_cosim` 的模式识别、依赖失效与实机证据。

- [ ] 添加失败用例：`test_self_link_reuses_actual_em_block`、`test_port_mode_polarity_must_match`、`test_network_change_invalidates_downstream`、`test_transient_cosim_requires_two_sided_evidence`、`test_harmonic_curve_alone_does_not_verify_cosim`。
- [ ] 运行失败测试；实现 self 链接、端口/参数映射及两种模式的预检和执行，再跑测试。
- [ ] 按设计 §6.4 的实际参数生成三维预览、端口表及电路图，交用户审阅；在审阅前不创建该几何。
- [ ] 几何审阅通过后按阶段构建/rebuild/读消息/保存；单独核验几何与端口。
- [ ] 完成 V3：三维裸线网络、线性负载、独立网络加载计算对照。
- [ ] 完成 V4：真实瞬态耦合读回、两侧执行证据、波形/负载反馈及线性数值比较。
- [ ] 完成 V5：内置二极管→已知 SPICE 子电路；0.1/1 V；非线性及网格/时间步收敛。若 SDK/许可不足，明确终止相关能力并记录，不能用 network 冒充。
- [ ] 各阶段分别建立本地提交和验收记录，最终能力名称按已通过范围公布。

## Task 5：外部工程、依赖闭包与可搬运性

**Consumes:** 已核验的 self 链接、依赖 manifest schema 和三维/电路运行身份。

**Produces:** `link_em` 外部来源分支；`inspect_dependencies()`；`bundle(destination)`。

- [ ] 添加失败用例：`test_missing_spice_include_is_reported`、`test_external_project_cycle_is_rejected`、`test_bundle_relocates_supported_links`、`test_bundle_collision_does_not_overwrite_source`、`test_unknown_dependency_prevents_portable_claim`。
- [ ] 运行失败测试；实现支持格式的依赖枚举/复制/重定位，保留来源/hash和参数/端口映射，再跑测试。
- [ ] 完成 V6：移动到第二个工作目录、重开读回并重算；按 network/transient_cosim 分别记录支持或限制。
- [ ] 缺失 SPICE 文件仅在工作副本中模拟；未验证来源不作为默认回退；本地提交。

## Task 6：服务和 MCP 显式接入

**Consumes:** Tasks 1–5 的 Python API；既有 `RunService` 和工具注册协议。

**Produces:** `register_circuit_handlers(service)`、`register_circuit_tools()` 及设计 §5 的六个工具。

- [ ] 按已经实现并实测的范围最终同步 `docs/PUBLIC_API.md`，再修改 service/MCP 协议。
- [ ] 添加失败用例：`test_explicit_registration_preserves_existing_handler`、`test_non_circuit_jobs_delegate`、`test_unknown_operation_rejected`、`test_sdk_access_stays_on_worker`、`test_unverified_maps_to_failed_with_evidence`、`test_failed_result_preserves_artifacts`、`test_duplicate_request_does_not_execute_twice`、`test_tools_do_not_send_vba`。
- [ ] 运行失败测试；实现 workflow 路由、兼容失败证据字段和显式 MCP 注册；不新增任务 kind/status。
- [ ] 对六个工具逐一确认 schema、读写标注、request ID 与受限路径；以真实服务运行 V3/V4 最小样例，校验任务号与两侧运行身份一致。
- [ ] 进行 MCP stdio 握手和最小工具调用验收，日志不进入 stdout；本地提交。

## Task 7：完整回归、健壮性和交付

**Consumes:** 所有阶段报告、源工程与已保存的结果。

**Produces:** 可安装制品、使用指南、逐模式/逐版本验收矩阵和已知限制。

- [ ] 完成 V7 的 A→B→A、旧结果拒绝、模式不符、缺模型、错误映射、缓存核验、服务中断恢复、attach 归属检查。
- [ ] 阻塞/弹窗先离线注入；实机观察按仓库规则保存标题、正文、按钮、PID；无证据不自动操作。
- [ ] 默认离线回归：`.venv/Scripts/python.exe -B -m pytest -o addopts='' -m 'not gui and not cst_live' -q`。临时文件与缓存设置到 `work/`；不能因为 marker 缺失误触发实机。
- [ ] 实机脚本使用 `cst_live` 标记、明确开关和单阶段选择；固定输入、资源限制与预览审批记录后运行。默认收集/导入不得连接 CST。
- [ ] 在 `.venv` 构建 wheel/sdist；在本仓库 `work/` 下的隔离安装环境验证包导入、类型文件、新接口、无 CST 时的明确错误和惰性行为；制品不含工程/模型/实机产物。
- [ ] 更新 `docs/VALIDATION.md`：列真实 CST build、每个 V 阶段状态、产物路径、两种模式的支持矩阵；保留历史离线记录，不改写为实机成功。
- [ ] 更新使用指南、README 和最终版本 `0.2.0`；核对当前并发修改，不覆盖无关工作；仅提交本次相关文件，不自动推送。

## 审阅后执行边界

建议用户一次确认本设计的目标范围、阶段顺序、候选基准与容差，再执行协议/离线开发和必要的 SDK 验证。三维样例在真实预览完成并获审阅后进入建模/求解；正常通过的后续依赖步骤无需重复询问。

若实测发现官方文档接口在当前 build 不可用，先完成不受影响的步骤并记录证据；仅对需要改变范围、数值验收规格或资源级别的方案重新提交审阅。
