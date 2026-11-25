# 整库规则迁移对照表

本表供仓库维护者查找原规则。工作时从[任务索引](../skills/README.md)进入，索引按交付物列出当前技能和各自的触发条件。仓库边界见[项目约定](../AGENTS.md)。[本次验证记录](validation/rule-routing.md)列出验收条件与结果。

盘点基线包含 118 个受版本管理的 Markdown 文件。根目录 4 个，文档目录 73 个（含 44 份指南、15 份历史计划和设计），技能目录 39 个（1 份索引、14 个技能入口、24 份参考），另有插件说明和实机测试说明各 1 个。另核对了规则涉及的运行库实现、CI 测试选择、构建脚本与清单。

| 原位置或重复内容 | 现行位置 | 使用时机与保留的约束 |
|---|---|---|
| 根约定与多份技能重复的阅读说明、机器示例 | [项目约定](../AGENTS.md)、[任务索引](../skills/README.md#完整阅读规则) | 读完所选入口和当次操作要求的引用，截断时补齐。跨包协议、显式注册、SDK 延迟加载、迁移源只读及验证等级继续生效。 |
| 许可证故障后的升级重试、散落的 Python 启动示例 | [执行环境](../skills/README.md#执行环境)、[诊断](../skills/cst-diagnostics/SKILL.md)、[后台启动器](../skills/keysight-ads-simulation/scripts/invoke_hidden.ps1) | 从首次原生 CST 或 ADS 操作使用获准的许可宿主，包括直接读原生结果。Windows 非交互进程在后台运行，保留退出码与日志，CST 自己的诊断窗口保持可见。已导出文件可离线处理。 |
| 根约定、会话总说明中的恢复、关闭及长期任务要求 | [会话入口](../skills/cst-sessions/SKILL.md)、[工程生命周期](../skills/cst-sessions/references/project-lifecycle.md)、[会话故障恢复](../skills/cst-sessions/references/session-operations.md) | 首先识别原工程、进程、worker、任务与回执。单个工程的清理、释放所有者及关闭整个环境分别判断授权。未知写入先恢复原任务，防止重复执行。 |
| 工程清单与服务端检查混写 | [工程清单](../skills/cst-sessions/references/workflow-checkpoint.md)、[受管工作流](guides/workflow_enforcement.md) | 跨轮任务恢复参数和输入依赖，纠正后更新清单；依赖阶段提交前调用方检查当前证据。已绑定工程还接受服务与 worker 检查。 |
| 建模、网格规则及一次性器件例外 | [建模](../skills/cst-modeling/SKILL.md)、[网格与频率](../skills/cst-mesh-frequency/SKILL.md) | 先以实际参数预览并取得审阅，再按依赖顺序写入。器件专属例外只随对应工程的授权和证据使用；网格和端口检查按实际结构触发。 |
| 单次已有工程 EM、参数刷新和完整重建混写 | [仿真](../skills/cst-simulation/SKILL.md)、[公开接口](PUBLIC_API.md)、[已保存基线](../skills/cst-simulation/references/saved-baseline.md)、[EM 交接](../skills/cst-simulation/references/em-handoff.md) | 已审阅且无在途冲突的单次 EM 可直接运行；有待保全结果时区分参数刷新与完整重建，并回读真实 Run ID、参数组合和曲线。 |
| 参数研究入口把配置、执行、导出写成连续动作 | [参数研究](../skills/cst-parameter-study/SKILL.md)、[结果导出和历史](../skills/cst-results/references/exports-and-history.md) | 服务器交接只配置、核对并保存。另行请求执行时核实执行入口；导出已有数据需核验运行身份、端口与矩阵完整性。 |
| 场路长入口中的静态 SP、HB、模板和取消流程 | [场路入口](../skills/cst-circuit/SKILL.md)、[探索性静态 SP](../skills/cst-circuit/references/exploratory-static-sp.md)、[HB 与后处理](../skills/cst-circuit/references/hb-and-postprocessing.md)、[场路指南](guides/circuit_cosimulation.md) | 按任务选择静态或大信号步骤。区分模板配置、保存重开与实际执行。首错停止、工程和任务身份、明确 CST HB 启动授权继续生效。 |
| 二极管接口、器件性能和隔离器示例交叉重复 | [二极管加载](../skills/cst-diode-loading/SKILL.md)、[器件表征](../skills/cst-device-characterization/SKILL.md)、[隔离器交接](../skills/diode-isolator-design-workflow/references/engineering-handoffs.md) | 加载时核对实体、引脚、极性；评估时查实际逐管 VAK(t)。EM→同工程静态 SP→SNP→ADS HB 按要求绑定来源、方向、模型及偏置。 |
| ADS 原生运行、无界面验收与图形交付 | [原理图](../skills/keysight-ads-schematic/SKILL.md)、[电路仿真](../skills/keysight-ads-simulation/SKILL.md)、[数据与显示](../skills/keysight-ads-results/SKILL.md)、[版图与制造](../skills/keysight-ads-layout/SKILL.md) | 原生操作走许可宿主并后台启动。无界面任务按数据验证；用户要求的 ADS 原生显示按交付项单独检查。 |
| 原生读结果、CSV 绘图、求解或现场验收混用 | [结果读取](../skills/cst-results/SKILL.md)、[绘图](../skills/cst-figures/SKILL.md)、[现场验证](../skills/cst-in-situ-validation/SKILL.md) | 导出文件、原生只读、几何检查和实际求解分别记录。已有结果分析仅使用所需读取路径；图像和离线测试各保留其证据等级。 |
| 诊断入口堆叠不同类型的故障 | [诊断](../skills/cst-diagnostics/SKILL.md)、[窗口处理](guides/cst_dialogs.md)、[停止作用域](guides/solver_stop_scope.md) | 有阻塞才读对应处置。读实际标题、正文、按钮与所属进程，检查求解状态，不因超时或窗口消失推断成功。 |
| 历史设计、计划中的批准语和旧数量 | [历史计划](superpowers/plans/)、[历史设计](superpowers/specs/)、[验证台账](VALIDATION.md) | 保留当时决策、来源和证据；每个历史计划或设计入口标出适用日期。新工程的启动、改写、例外按当次授权判定。 |
| 插件构建与维护文档重复描述发布内容、测试范围 | [构建脚本](../scripts/build_plugin.py)、[发布指南](guides/codex-plugin.md)、[贡献指南](../CONTRIBUTING.md) | 随插件提供技能实际依赖；历史、维护和开发材料留在仓库。离线与真机验收独立记录，安装后核对实际版本与文件。 |

“低频”按适用工况判断。归档恢复、异常弹窗、HB 模板、专项网格等仍保留完整操作要求；没有使用频率统计的数据不据此作删除判断。
