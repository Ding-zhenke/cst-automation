# 仓库工作约定

## 开始任务

先读[技能索引](skills/README.md)，再读完所选技能和当前操作的必读引用。截断须连续补齐；压缩后只剩摘要时恢复全文与当前要求，再提交依赖的模型写入或求解。技能统一维护在仓库根目录 `skills/`。

## 开发与发布

- 本库负责通用 CST 建模、仿真、结果、任务服务和诊断。保持 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，共享数据 API 放在 `cst_automation`。通用包禁止导入 `mesh_grid`、`topo_modeler`、`topo_templates`、`tpc_toolkit`、`em_enclosure`。
- 普通 Python 导入保持离线，真实操作才加载 CST 自带的 SDK。`cst` 不列为 PyPI 依赖。跨包协议变更先更新 [PUBLIC_API.md](docs/PUBLIC_API.md)，handler 和 MCP 扩展显式注册。
- 用本仓库 `.venv` 或隔离测试目录。迁移源 `D:\成电博士生涯\自动建模算法尝试\TPC` 严格只读。不得修改相邻仓库、公共 Python 或用户全局 MCP 配置。备份、构建、测试和开发产物留在仓库，`work/` 忽略且不发布。
- 主会话统一提交并推送到 `main`，其他分支须用户另行指定。离线测试、构建和发布见[贡献指南](CONTRIBUTING.md)，实机验收范围以[验证记录](docs/VALIDATION.md)为准。

## 工程操作

- 本机首次原生 CST 或 ADS 命令就在有许可证的宿主运行，Codex 命令指定 `sandbox_permissions="require_escalated"`。已有工程的单次 EM 也适用。Windows 非交互 Python 从首进程起用[后台启动脚本](skills/keysight-ads-simulation/scripts/invoke_hidden.ps1)，保留输出、错误、退出码及 CST 诊断弹窗。
- 实际 CST 操作默认走[所属会话](skills/cst-sessions/SKILL.md)。每个对话独立绑定引用、worker、DE 和工程目录，会话根固定为本仓库 `work/sessions`。没有会话 MCP 时用同一 `.venv` 的 CLI。核对基线、授权及在途任务，按原引用恢复，禁止无 PID 附加、重放未知写入或为重试复制工程。
- 已有工程的单次 EM 可直接在宿主 `setup(path)`、`app.run()`，先查工程及既有任务状态，以日志和实际结果判断。跨轮建模、EM→HB 与优化按[阶段清单](skills/cst-sessions/references/workflow-checkpoint.md)保存和恢复要求，纠正输入后更新，依赖阶段提交前核对。
- 几何写入前按真实参数出预览并等待审阅。依赖阶段分别重建、读取消息、核对产物。遇到弹窗先核对标题、正文、按钮及进程归属。配置、几何、原生读回、实际求解、数值收敛和性能分别给证据。离线通过、超时或关闭弹窗都不能证明求解成功。
- 当前任务确需 Computer Use 时，优先将界面操作委派给 `gpt-6.1-terra`，由主会话给出目标、限制并核查结果。若环境不支持则说明限制，在原有权限和确认范围内继续。
- 只有用户要求才关闭整个 CST 环境。正式交付与依赖核验后，按[工程生命周期](skills/cst-project-lifecycle/SKILL.md)保存、关闭并退休本任务的过程工程，确认路径和回执后清理。状态未知、正式文件、必需依赖及用户要求保留的文件均受保护。
