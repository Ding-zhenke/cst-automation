---
name: cst-circuit
description: Configure or run CST Design Studio circuit analysis tasks, including existing static SP, network or transient field-circuit co-simulation, and native HB cross-checks.
---

# CST 电路任务与场路联合

完整阅读本入口及当前操作要求的引用章节，按[完整阅读规则](../README.md#完整阅读规则)补读和恢复。

## 选择任务

- **配置或运行已有电路任务**时，先确定工程、任务名、分析模式与交付物。实际操作使用[所属会话](../cst-sessions/SKILL.md)和[许可宿主、后台启动器](../README.md#执行环境)。通过受支持的原生 API 设置与提交；必要的原生命令依官方文档核实。缺少接口时记录具体缺项，真实阻塞弹窗按[诊断](../cst-diagnostics/SKILL.md)处理。若交付物是原理图、元件位置、引脚或连线，直接使用 [Design Studio 原理图](../cst-schematic/SKILL.md)。
- **常规 HB 验证和扫频默认用 [ADS](../keysight-ads-simulation/SKILL.md)**。从已验收的 CST EM 导出 Touchstone，保持端口、参考阻抗、偏置、泵浦和探测条件一致；双音有限功率和泵浦小信号分别报告。按[ADS 双音 HB 参考](references/ads-hb.md)处理版本、谱线和日志。
- **CST Design Studio HB 用于交叉核对或定位差异，须用户明确要求启动 CST HB 后才提交。** 只读已有结果、配置和保存 HB 扫描均在相应授权内完成。只配置时不为验收运行 EM、DC、网格、HB、扫描或 Post 模板。

## 配置、运行和读取

1. 核对指定任务所用的电路、端口、源、负载、频率或时间范围与 EM 依赖。只配置时保存并读回请求的设置；要求运行时核对适用于该任务和当前绑定的执行入口。
2. 对受管的参数→EM→HB 链，按[工作流契约](../../docs/guides/workflow_enforcement.md)绑定规格。服务在提交与执行时核对当前成功 EM 回执、已接受的数值报告和原生设置。调用方仍须分析原始数据，检查专业条件。多轮任务先恢复[要求与证据清单](../cst-sessions/references/workflow-checkpoint.md)，核对源/负载、矩阵、扫描轴和模板输入，在依赖阶段提交前运行清单检查。
3. 对使用 `run_checked` 的任务，提交真实任务名、模式、结果树路径与整数 run_id，常规新运行用 `reuse="never"`。对已绑定的静态 SP，使用与实际拓扑和源条件相符的受管入口；带指定 50 Ω 控制链的零偏流程按[静态 SP 执行契约](../../docs/guides/diode_workflow_integration.md#native-zero-bias-sp-gap)核实适用性。用 `inspect_dependencies` 核对依赖路径及摘要，并按任务日志和 schematic 域的 `CircuitResult` 验证本次运行及实际结果。
4. **启动 CST HB 或父扫描前**完整阅读[HB 放行与首错停止](references/hb-and-postprocessing.md#hb-运行前的放行门槛)。逐块核对 DC 至全部保留混频的实际数据覆盖；拓扑或 EM 输入改变后先验证双向代表工况的工作点、实际入射、匹配与谱线。首个初始化或数值失败即停止后续组，缺有效输入的下游模板跳过。停止或中断后按[3D 与 DS 的空闲边界](../../docs/guides/solver_stop_scope.md)查目标序列及回执。
5. **评估二极管**时，与 S 参数及性能指标一并交付各管实际 A−K 总电压 VAK(t)、工况与来源。分量、相位、公共源时钟、自动出图及缺项按[逐管电压交付](../cst-device-characterization/references/signals-and-evidence.md#逐管电压交付)核对；当次明确缩小范围按其要求。只分析已有数据时不额外求解。

## 按操作读取

| 操作 | 在该操作前阅读 |
|---|---|
| 设置瞬态激励、积分时间、EM 时间步或周期稳态 shooting | 按当前任务读[时间与输出采样](../../docs/guides/circuit_cosimulation.md#实际积分时间与输出采样)、[端口激励](../../docs/guides/circuit_cosimulation.md#端口激励源阻抗和无源负载)、[EM 时间步](../../docs/guides/circuit_cosimulation.md#em-时间步与每步输出配置)或[周期稳态配置](../../docs/guides/circuit_cosimulation.md#周期稳态射击法配置)。 |
| 已保存 EM 与 abort 矛盾、MOR/DC 文件块或内嵌网络交接 | [资格核验、完整矩阵及端口映射](../../docs/guides/saved_em_qualification.md)。分别核对原失败回执、实际低频样本、显式物理端口顺序与原生阻抗。 |
| 使用明确指定的未收敛 EM 做探索性静态 SP | [静态 SP 专用范围和失败接续](references/exploratory-static-sp.md)。 |
| 在 DS 的 Post 任务中添加 CST 自带模板，例如静态 SP 完成后自动导出 Touchstone | 按[结果模板配置](../cst-result-templates/SKILL.md)选 Design Studio 分支，核对源 SP、目标 Post 与序列顺序。 |
| 禁用已有 HB 父/子任务 | [受管禁用](../../docs/guides/disable_native_tasks.md)。初检所有目标，依次从子到父写入各步读回，仅保存配置。 |
| 配置原生 HB 扫频与方向、绑定自动后处理、更新已有模板 | [原生 HB 扫描与后处理](../../docs/guides/native_hb_postprocessing.md)及[自动刷新与保留历史](../../docs/guides/hb_parametric_storage_and_length_results.md)。核对父子绑定、源表达式、HB→Post 顺序和实际 Run ID，替换序列须确认范围。交付自动出图时，按[工程模板适配](references/hb-and-postprocessing.md#模板适配当前工程)分别验证配置、保存关闭重开的归档持久性及授权后的实际回调。 |
| 原生 Update 异常或 Post 回调定位错误 | [异常与运行身份](../../docs/guides/circuit_update_and_result_identity.md)，固定正 ID 的参数需查[工程绑定查询](../../docs/guides/project_bound_run_parameter_bridge.md)。 |
| 选择 HB 并行度 | [HB CPU 并行设置](references/hb-and-postprocessing.md#hb-cpu-并行设置)。 |
| 通用电路与同工程 EM 参数研究 | 优先选能表达所需轴、依赖、输出的原生扫描。确需逐点决策或特定归档再用[逐点 study 及历史比较](references/parameter-studies.md)，它会保存并求解。 |
| 普通网络瞬态、强制 MOR 复用或可取消截止 | [任务运行与停止条件](../../docs/guides/circuit_cosimulation.md#任务运行与停止条件)。 |
| 对照 HB 与独立瞬态 | [共同观测量、频点和差值](../cst-device-characterization/references/signals-and-evidence.md#hb-与瞬态结果对照)。 |
| 开发 service/MCP、打包依赖、查实机证据 | [服务接口与发布范围](../../docs/guides/circuit_cosimulation.md#服务和-mcp)；公共协议见仓库 `docs/PUBLIC_API.md`，实际验收见 `docs/VALIDATION.md`。 |

具体尺寸、材料、二极管参数、扫描点和器件结论保存在用户工程。只在当前授权的工程工作中验证功能；维护时使用所需离线检查，保留原门槛和已有验证边界。
