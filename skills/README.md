# 按任务选择 CST 与 ADS 技能

## 完整阅读规则

读完所选 `SKILL.md` 和当前操作标为必读的引用章节，再执行依赖它的写入或求解。按当前工况选择引用；其他分支留待触发时读取。搜索命中、文件头、哈希、已读标记和历史摘要都不能代替原文。输出截断时连续补齐缺段。上下文压缩后若只剩摘要，先重新读取相关规则、恢复工程要求；已完整保留且未改的原文可继续使用。由执行者主动完成，无需用户提醒。

仓库维护使用根目录 `skills/`，安装版使用该插件自带技能。首次记录实际选用的技能路径和运行库模块位置；检查正在运行的 worker 能力，避免混用副本或为加载新版中断工程。

## 执行环境

本机首次原生 CST 或 ADS 调用使用能访问许可证的沙箱外宿主。Codex shell 命令从第一次起指定 `sandbox_permissions="require_escalated"`，包括 CST SDK 导入、`doctor --probe`、原生 worker 启动或恢复、连接与打开工程、原生读结果、求解，以及 ADS 原生操作。已有经授权的宿主服务可复用所属 worker。工程写入和求解另按用户授权范围执行。普通 `doctor --json`、已导出 CSV/Touchstone、日志和 fake 测试可在沙箱内执行。

Windows 非交互 Python 从第一个进程起使用[后台启动脚本](keysight-ads-simulation/scripts/invoke_hidden.ps1)。按所选仓库或插件解析脚本，保留工作目录、独立参数、输出、错误和退出码；长任务继续跟踪原进程或任务。交互终端只在用户要求时显示，CST 诊断窗口保持可见。以下为仓库根目录下的离线检查：

```powershell
& .\skills\keysight-ads-simulation\scripts\invoke_hidden.ps1 -Executable .\.venv\Scripts\python.exe -ArgumentList @('-m', 'cst_solver', 'doctor', '--json')
exit $LASTEXITCODE
```

## 任务入口

| 当前请求 | 首选技能 | 何时追加 |
|---|---|---|
| 读取已导出 CSV 或 CST 原生结果、导出已保存扫参矩阵 | [结果读取](cst-results/SKILL.md) | 绘图追加绘图技能；在线读取追加所属会话。读取请求不授权重算。 |
| 按分类和名称添加 CST 自带结果模板，例如 S-Parameters → Touchstone Export | [结果模板用法](cst-results/references/exports-and-history.md#install-touchstone-export-in-the-cst-project)和[结果技能](cst-results/SKILL.md) | 3D 选工程级模板；Design Studio 指定源 SP 和目标 Post 任务。 |
| 单次运行已有、已审阅的 EM 工程 | [EM 仿真](cst-simulation/SKILL.md) | 可直接在宿主运行 `setup(path)`、`app.run()`。已有绑定或在途工作按原身份处理。 |
| 配置服务器扫描或选择逐点控制 | [参数研究](cst-parameter-study/SKILL.md) | 准备服务器任务只配置、核对并保存。启动与结果导出有各自入口。 |
| 建模、改几何、材料、端口 | [建模](cst-modeling/SKILL.md) | 实际写入用所属会话；真实参数预览经审阅后再分阶段构建。 |
| 选择网格、频率采样或自适应策略 | [网格与频率](cst-mesh-frequency/SKILL.md) | 按求解器和所改设置读取专项说明。 |
| 绑定、恢复、交接或清理工程 | [持久会话](cst-sessions/SKILL.md) | 未知写入先查原任务、状态、回执；发生弹窗或停滞再读诊断。 |
| SDK、许可证、阻塞或弹窗 | [诊断](cst-diagnostics/SKILL.md) | 按实际窗口类型和进程归属选择恢复流程。 |
| Design Studio 原理图、静态 SP、场路协同、原生 HB | [场路联合](cst-circuit/SKILL.md) | HB 验证默认 ADS；只有用户明确要求启动 CST HB 才提交。 |
| 创建、打开或编辑 ADS 原理图，把静态参数复制到 HB 供手调 | [ADS 原理图](keysight-ads-schematic/SKILL.md) | 核对目标 cell、保存值和网表。要求打开窗口时追加桌面 API 章节。 |
| 配置或运行 ADS DC、SP、HB、原生扫频或优化 | [ADS 电路仿真](keysight-ads-simulation/SKILL.md) | 仅配置时止于控制器和网表核对；运行时核对本次日志、数据集及完整扫描轴。 |
| 读取已有 ADS `.ds`、提取曲线、生成或打开 `.dds` | [ADS 结果与显示](keysight-ads-results/SKILL.md) | 读数止于已保存的数据；要求原生显示窗口时追加窗口核验。 |
| ADS LineCalc、物理版图、Momentum/RFPro、DRC、Gerber/Drill | [ADS 版图与制造](keysight-ads-layout/SKILL.md) | 按尺寸、版图、EM 配置或求解、制造文件选择相应章节。 |
| ADS 启动异常、许可错误、`fopen(NULL)`、Get Started 弹窗或 exit hangs | [ADS 故障诊断](keysight-ads-simulation/references/troubleshooting.md) | 按现象读取对应诊断章节；使用 Agent Bridge 时查[桥接说明](keysight-ads-simulation/references/ads-agent-bridge.md)。 |
| 二极管建模、接口、极性、偏置 | [二极管加载](cst-diode-loading/SKILL.md) | 做性能评估时追加表征。 |
| 工况、指标、逐管电压或性能结论 | [器件表征](cst-device-characterization/SKILL.md) | 二极管评估交付实际 VAK(t)、相应指标和来源。 |
| 几何预览与科研图 | [绘图](cst-figures/SKILL.md) | 使用实际参数和结果；输出图片本身不授权工程变更。 |
| 隔离器 EM、同工程静态 SP、SNP 或 ADS HB 迭代 | [隔离器流程](diode-isolator-design-workflow/SKILL.md) | 按用户要求选择阶段，读取对应实现和证据要求。 |
| 实际工程中遇到可复用缺陷或获得实机证据 | [现场验证](cst-in-situ-validation/SKILL.md) | 在当前授权内修复、脱敏记录；额外专项求解需另有任务依据。 |

## 跨阶段提交

跨轮建模、EM→HB、优化或中断恢复，从工程工作目录的 [workflow.json 与检查器](cst-sessions/references/workflow-checkpoint.md)恢复身份、要求、输入及证据；用户纠正后先更新，再由调用方在依赖阶段提交前执行一致性检查。已绑定的参数→EM→HB 工程还执行[服务提交和 worker 执行检查](../docs/guides/workflow_enforcement.md)。只有当前输入的实际证据可放行下一阶段。简单文件读取及已有工程的单次 EM 不强制建立这套跨轮清单。
