---
name: cst-circuit
description: Use for CST Design Studio schematics, EM port links, network or transient field-circuit co-simulation, circuit results, built-in result templates on Post tasks, or their service and MCP interfaces.
---

# CST 场路联合

完整阅读本入口及当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

## 选择任务

- **原理图、网络和瞬态联合**使用 `app.circuit`。仅修改三维集总元件时转[建模](../cst-modeling/SKILL.md)或[EM 仿真](../cst-simulation/SKILL.md)。操作已有 CST 工程从[所属会话](../cst-sessions/SKILL.md)进入；本机首次原生调用即用经批准的宿主，通过[后台启动器](../keysight-ads-simulation/scripts/invoke_hidden.ps1)启动非交互 Python。原生 API、必要时有官方依据的 VBA 用于设置和提交，缺少能力时记录具体缺项，禁止借 Computer Use 配置、运行或绕过门槛。真实弹窗按[诊断](../cst-diagnostics/SKILL.md)检查归属、标题、正文和按钮。
- **常规 HB 验证和扫频默认用 [ADS](../keysight-ads-simulation/SKILL.md)**。从已验收的 CST EM 导出 Touchstone，保持端口、参考阻抗、偏置、泵浦和探测条件一致；双音有限功率和泵浦小信号分别报告。按[ADS 双音 HB 参考](references/ads-hb.md)处理版本、谱线和日志。
- **CST Design Studio HB 用于交叉核对或定位差异，须用户明确要求启动 CST HB 后才提交。** 只读已有结果、配置和保存 HB 扫描均在相应授权内完成。只配置时不为验收运行 EM、DC、网格、HB、扫描或 Post 模板。

## 配置、运行和读取

1. 在当前工程核对单位、元件类型、引脚、原生位置、端口、已有网络及依赖，明确 network 或 transient_cosim。使用[原理图配置指南](../../docs/guides/circuit_cosimulation.md#用户审批后的原理图操作)中的 schema、预览和增量写入方式。新建、补充或整理电路时，必读[紧凑布局与整图可读性](../../docs/guides/circuit_cosimulation.md#紧凑布局与整图可读性)：新 Block/ExternalPort 一律用 `native_position`，移动已有对象时用 `set_position(..., coordinate_space="native")`；旧 `position` 是 CST setter 坐标，不能再用于按图纸坐标排版。默认让相连模块靠近、支路贴近对应引脚，按符号与标签大小留间距；常见器件电路应在常用窗口和正常阅读缩放下看到全貌及可读标注，不能靠极度缩小视图交付。几何或端口改变须以实际坐标预览并等候审阅。重名、部分写入或断线保留已完成阶段、消息与回执，先核对现场。
2. 对受管的参数→EM→HB 链，按[工作流契约](../../docs/guides/workflow_enforcement.md)绑定规格。服务在提交与执行时核对当前成功 EM 回执、已接受的数值报告和原生设置。调用方仍须分析原始数据，检查专业条件。多轮任务先恢复[要求与证据清单](../cst-sessions/references/workflow-checkpoint.md)，核对源/负载、矩阵、扫描轴和模板输入，在依赖阶段提交前运行清单检查。
3. 在已保存的工作副本调用指定的 `run_checked`，提供真实任务、模式、结果树路径与整数 run_id，常规新运行用 `reuse="never"`。用 `inspect_dependencies` 核对依赖路径和摘要。从 schematic 域用 `CircuitResult` 列举路径及 run 身份，再读复数曲线、单位、参数和来源。保留实际项目、日志与未验证项；配置、保存读回、重开、求解和数值充分性分别记录。
4. **启动 CST HB 或父扫描前**完整阅读[HB 放行与首错停止](references/hb-and-postprocessing.md#hb-运行前的放行门槛)。逐块核对 DC 至全部保留混频的实际数据覆盖；拓扑或 EM 输入改变后先验证双向代表工况的工作点、实际入射、匹配与谱线。首个初始化或数值失败即停止后续组，缺有效输入的下游模板跳过。停止或中断后按[3D 与 DS 的空闲边界](../../docs/guides/solver_stop_scope.md)查目标序列及回执。
5. **评估二极管**时，与 S 参数及性能指标一并交付各管实际 A−K 总电压 VAK(t)、工况与来源。分量、相位、公共源时钟、自动出图及缺项按[逐管电压交付](../cst-device-characterization/references/signals-and-evidence.md#逐管电压交付)核对；当次明确缩小范围按其要求。只分析已有数据时不额外求解。

## 按操作读取

| 操作 | 在该操作前阅读 |
|---|---|
| 新建或补连原理图、移动块、链接 EM、设置 transient 源与模型、EM 时间步或周期稳态 shooting | [场路接口指南](../../docs/guides/circuit_cosimulation.md)，到对应操作章节核对 API、读回和编辑范围。 |
| 已保存 EM 与 abort 矛盾、MOR/DC 文件块或内嵌网络交接 | [资格核验、完整矩阵及端口映射](../../docs/guides/saved_em_qualification.md)。分别核对原失败回执、实际低频样本、显式物理端口顺序与原生阻抗。 |
| 使用明确指定的未收敛 EM 做探索性静态 SP | [静态 SP 专用范围和失败接续](references/exploratory-static-sp.md)。 |
| 在 DS 的 Post 任务中添加 CST 自带模板，例如让静态 SP 完成后自动导出 Touchstone | 用 `app.add_builtin_result_template` 设置目标 `post_task` 和源 SP 的 `settings["TaskName"]`。见[调用示例与 SP → Post 顺序](../cst-results/references/exports-and-history.md#install-touchstone-export-in-the-cst-project)。 |
| 禁用已有 HB 父/子任务 | [受管禁用](../../docs/guides/disable_native_tasks.md)。初检所有目标，依次从子到父写入各步读回，仅保存配置。 |
| 配置原生 HB 扫频与方向、绑定自动后处理、更新已有模板 | [原生 HB 扫描与后处理](../../docs/guides/native_hb_postprocessing.md)及[自动刷新与保留历史](../../docs/guides/hb_parametric_storage_and_length_results.md)。核对父子绑定、源表达式、HB→Post 顺序和实际 Run ID，替换序列须确认范围。交付自动出图时，按[工程模板适配](references/hb-and-postprocessing.md#模板适配当前工程)分别验证配置、保存关闭重开的归档持久性及授权后的实际回调。 |
| 原生 Update 异常或 Post 回调定位错误 | [异常与运行身份](../../docs/guides/circuit_update_and_result_identity.md)，固定正 ID 的参数需查[工程绑定查询](../../docs/guides/project_bound_run_parameter_bridge.md)。 |
| 选择 HB 并行度 | [HB CPU 并行设置](references/hb-and-postprocessing.md#hb-cpu-并行设置)。 |
| 通用电路与同工程 EM 参数研究 | 优先选能表达所需轴、依赖、输出的原生扫描。确需逐点决策或特定归档再用[逐点 study 及历史比较](references/parameter-studies.md)，它会保存并求解。 |
| 普通网络瞬态、强制 MOR 复用或可取消截止 | [任务运行与停止条件](../../docs/guides/circuit_cosimulation.md#任务运行与停止条件)。 |
| 对照 HB 与独立瞬态 | [共同观测量、频点和差值](../cst-device-characterization/references/signals-and-evidence.md#hb-与瞬态结果对照)。 |
| 开发 service/MCP、打包依赖、查实机证据 | [服务接口与发布范围](../../docs/guides/circuit_cosimulation.md#服务和-mcp)；公共协议见仓库 `docs/PUBLIC_API.md`，实际验收见 `docs/VALIDATION.md`。 |

具体尺寸、材料、二极管参数、扫描点和器件结论保存在用户工程。只在当前授权的工程工作中验证功能；维护时使用所需离线检查，保留原门槛和已有验证边界。
