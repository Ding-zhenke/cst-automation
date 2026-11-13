# Codex 多 skill 插件

一个 `CST Automation` 插件包含十四个独立 skill：

| Skill | 按需使用的场景 |
| --- | --- |
| `cst-modeling` | 几何规划、预览、建模与检查 |
| `cst-simulation` | 对已审阅工程配置并运行求解 |
| `cst-mesh-frequency` | 电尺寸评估、频率采样与网格自适应决策 |
| `cst-parameter-study` | 参数扫描范围与原生线性、对数、离散扫描 |
| `cst-circuit` | Design Studio 原理图、场路任务和电路结果 |
| `cst-sessions` | 持久 CST 会话、工程恢复与生命周期 |
| `cst-device-characterization` | 器件评价工况、指标和证据化报告 |
| `cst-diode-loading` | 二极管表示、偏置/接口、寄生和数值有效性 |
| `cst-figures` | 科研绘图、几何预览和可复现样式 |
| `cst-results` | 读取、导出和分析结果 |
| `cst-diagnostics` | 安装、SDK、弹窗与任务故障诊断 |
| `cst-in-situ-validation` | 在实际工程中验证、修复并回馈通用接口 |
| `keysight-ads-simulation` | ADS 电路、HB 数据和 CST 到 ADS 的数据交接 |
| `diode-isolator-design-workflow` | 协调二极管隔离器的 CST EM、原生 SP、ADS HB 与证据化迭代 |

宿主先获取各 skill 的名称和描述，再按任务读取相关 `SKILL.md`；一个任务可以先后使用多个 skill。不合并指令，也不增加要求每次加载全部 skill 的总入口。保持默认自动选择策略，也可在宿主支持的 skill 选择器中明确指定某个 skill。最终选择由宿主和模型决定，插件不提供确定性的关键词路由或逐 skill 的开关。

## 构建

在仓库根目录使用本仓库虚拟环境：

```powershell
.\.venv\Scripts\python.exe scripts/build_plugin.py
```

产物是 `dist/cst-automation-plugin.zip` 和用于本地安装的 `dist/cst-automation-marketplace.zip`。清单源文件位于 `plugins/cst-automation/.codex-plugin/plugin.json`；它是打包模板，该源目录尚未包含 skills，不能直接当成完整插件安装。

插件压缩包根目录含原生 `plugin.json`、兼容 `.codex-plugin/plugin.json`、`skills/`、`docs/` 和 `LICENSE`；marketplace 压缩包则包含本地目录清单和同一份完整插件。两份清单由同一模板生成，身份和版本一致；原生清单的 OpenAI 展示设置放在 `extensions.com.openai.interface`。每个 skill 逐字节复制，文档保留原有层级，使 `../../docs/...` 相对引用在插件内继续有效。新增 `skills/<name>/SKILL.md` 后重新构建会自动纳入。`dist/` 已由 Git 忽略，不维护生成文件的第二份源码。

## 使用与边界

0.3.25 将完整读取要求放到每个技能入口的前部，并明确输出截断补读、上下文压缩后
恢复全文及补齐前不执行依赖操作。`-TotalCount`/搜索摘要不能代替完整入口和所需引用
章节。此版本是执行指令强化，不包含宿主工具拦截器，也不以“已读”回执证明模型理解。

0.3.24 增加跨轮次要求/证据清单与只读一致性检查脚本，补齐几何参数覆盖、阻抗四层
区分、整机网格成本复核及后处理节点适配。插件包现在包含 `skills/README.md`。
检查脚本由工程调用方显式执行，不是 service/MCP 求解接口的强制拦截层。
源码、构建包、宿主已安装版本和运行中 worker 四者分别核对；不因构建完成声称
活跃对话已加载新版。多份同名 skill 以本轮选定的来源为准，避免混用旧用户级副本。

0.3.21 新增实际工程中验证和迭代自动化的 skill，并明确电路规格校验与预览
函数的子模块导入路径；完整张量材料会话路由需同步更新 Python 运行库，插件本身不包含运行库。

0.3.9 修复单 Python M0D 模块执行后多输出清单被误判为多个注册的问题；替换前
重新读取完整注册摘要。输出清单仍不代表回调计算正确，未知格式和多模块继续拒绝。

0.3.8 补充实机证据及结果身份规则：正数 Run ID 也可能被同参数重算覆盖，保存
执行记录须保留结果、日志、参数和内容摘要；Qt 结果失效选项在确认选择生效后再提交。
F CPU wrapper 已有原生调用与运行日志证据，仍不代替网格或器件性能验收。
同时明确全局 tetrahedral 控制仍经 legacy Mesh 路径，活动 HF Tet 组的实际生效
尚待读回；配置回执与技能不将历史命令提交提升为网格密度已改变。

0.3.5 增加 F 求解器 CPU 并行配置规则：通过 `configure_fd_parallelization`
设置线程和 socket 数，使用所属会话 `model_api`；实际使用量仍需原生日志验证。
它与时域 `Solver`、DS HB 和 GPU 配置分开；执行接口需要同步更新通用运行库。

0.3.4 修复覆盖升级时根清单残留旧版本的问题。解压发布包须同时更新根
`plugin.json` 与兼容清单，再运行插件安装命令并核对其返回版本，不能仅凭源文件
已更新或建议重启就认定新版已安装。根清单是优先身份来源，布局依据
[官方插件打包文档](https://developers.openai.com/plugins/build/plugins)。

0.3.3 明确 EM 模型频段通过 `set_frequency_range("fmin", "fmax")` 引用工程参数，
会话使用已有 `model_api` 路由；F 求解器采样区间仍是独立的数值设置。
频段表达式的引号修复位于 Python 运行库，更新 skill 时也须同步该运行库。

0.3.2 补充分阶段电路构建规则：已有元件的后续连线通过当前工程读回解析，使用
实际连接引脚名，界面显示标签单独保留。对应执行能力需要同步更新本机通用运行库；
纯 skill 插件不携带 Python 实现。

0.3.1 的默认建模流程是新器件从空工程开始，复用经审查的建模代码；绑定后的
续改、扫描和恢复仍使用同一工程。历史错误先读任务、CST 消息和弹窗文本，修正源
代码，仅在文本或程序化处理不足时使用 Computer Use。规则由 `cst-modeling`、
`cst-sessions`、`cst-diagnostics` 及其配套文档提供，保留默认按任务选择技能。

在 PowerShell 中可将 marketplace 包解压到一个长期保留的目录，然后添加并安装：

```powershell
Expand-Archive -LiteralPath .\dist\cst-automation-marketplace.zip -DestinationPath .\dist\cst-automation-marketplace
codex plugin marketplace add (Resolve-Path .\dist\cst-automation-marketplace).Path
codex plugin add cst-automation@cst-automation-local
codex plugin list --marketplace cst-automation-local --json
```

这些安装命令会修改当前用户的 Codex 插件配置和缓存；构建脚本本身不会安装插件。保持 marketplace 源目录可用，更新源码后重新构建并更新解压目录，按宿主提示刷新插件缓存。桌面端可在插件目录选择该 marketplace 并安装，具体步骤参见 [官方插件打包与本地测试说明](https://developers.openai.com/plugins/build/plugins)。

本版是纯 skill 插件，不包含 Python 运行库、CST SDK 或自动启动 MCP 的配置。执行指令前，目标工作环境仍需安装 `cst-automation`，真实操作需要匹配的 CST 环境；已有 MCP 服务可继续使用，见 [MCP 使用](mcp-usage.md)。插件文档不能代替运行库，也不能据此声称仿真通过。

原有仓库内与用户级 skill 可继续保留；若宿主同时发现多个来源的同名 skill，应在选择器里核对来源，避免把两份副本当作不同能力。此前的隔离 CLI 检查覆盖 marketplace 发现、插件安装和四个 skill 元数据可见；当前十四个 skill 的打包内容由仓库插件检查覆盖。实际对话中的自动选择和桌面端体验尚需单独验收。
