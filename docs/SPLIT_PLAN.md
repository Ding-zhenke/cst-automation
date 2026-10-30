# cst-automation 拆分与迁移实施计划

## 目标与边界

把原 TPC 仓库中的 CST 通用能力整理为独立 `cst-automation` 发行包，供 TPC 与 em-enclosure 单向依赖。保留 `cst_solver`、`tpc_service`、`cst_mcp` 的 Python 导入名；新增 `cst_automation.curves` 与 `cst_automation.s2p` 作为共享、无 CST 初始化的通用数据接口。TPC 专有的建模规则通过注册 handler 接入通用服务；通用包运行时不得导入 `mesh_grid`、`topo_modeler`、`topo_templates`、`em_enclosure` 或旧 `tpc_toolkit`。

来源是 `D:\成电博士生涯\自动建模算法尝试\TPC`，源 HEAD `51e4a63d302f0deea58d2a2df349892087dbdfe7`（2026-10-16）。源目录的 Git 工作树状态命令异常（`git status` 报 “not a work tree”），故迁移前后保存源文件哈希和可读的 Git 信息到忽略目录 `work/source-snapshot/`；不在源目录写入、清理、提交或更改远程。

## 已定接口与依赖方向

1. `cst_solver` 自行发现 CST Studio Suite 安装并产生可诊断错误；CST 附带的 `cst` Python 模块不声明为 PyPI 依赖。普通导入、离线解析和服务模块导入不得初始化 CST。
2. `tpc_service` 维护工程注册、单 worker 队列、任务状态/持久化、产物约束、错误和弹窗诊断。领域代码通过 `RunService.register_handler(kind, handler, *, replace=False)` 注册；handler 只用协议传入的 project、params、job 与 `Backend`，返回通用结果字典。handler 在进程内注册，不持久化、不自动导入、不跨线程传递 CST 会话。`build`/`study` 没有 handler 时给出 `domain_handler_missing` 及注册方式；通用 `solve` 只操作已有工程。
3. `cst_mcp` 默认工具面只包含通用服务/数据能力，领域工具可经 `register_tool(name, definition, handler, *, replace=False)` 扩展。未配置领域适配时，能力发现说明可执行通用任务；不得把拓扑模块作为隐式回退。MCP 写操作始终经过 `RunService`，不安装或改写用户 MCP 客户端配置。
4. `cst_automation.curves` 是连续带宽与采样点谐振规则的唯一实现；`cst_automation.s2p` 保持 `read_s2p_groups(filepath)` 行为。新旧 TPC 包由 TPC 仓库提供延迟兼容 shim，兼容代码不复制到本仓库。
5. 结构检查、CST readback、求解、性能/器件结论分别记录。offline/mock 不得标成真实 CST 验证；本轮不对用户工程执行真实求解。

## 实施顺序、文件归属与验收

| 阶段 | 主要输入 | 实施输出 | 验收 |
|---|---|---|---|
| 0. 源状态与计划 | 源 AGENTS、pyproject、API 文档、源码、源 HEAD | `work/source-snapshot/`、本文档、`docs/MIGRATION_MAP.md`、`docs/PUBLIC_API.md` | 快照含源 HEAD、remote、Git 状态错误、相关文件哈希；本仓库既有未提交骨架仍在 |
| 1. 发行与通用数据接口 | `cst_solver/`、`tpc_toolkit/curves.py`、`s2p.py`、原分析测试 | `pyproject.toml`、`cst_automation/{curves,s2p}.py`、类型标记、兼容测试 | 不安装 CST；函数签名和边界行为一致；wheel/sdist 含正确包 |
| 2. 通用 CST 底层 | `cst_solver` 全包、测试、通用 CST 文档 | 原导入名 `cst_solver`、类型文件与测试、安装/环境诊断文档 | 完整离线测试通过；安装发现/ABI/失败诊断证据独立记录；无 TPC 源码依赖 |
| 3. 通用任务服务 | `tpc_service` 状态机、worker、registry/store、backend、原测试 | 独立 `tpc_service`、handler 协议、fake backend 示例 | 状态、取消、串行、超时/弹窗与产物测试；缺 handler 给可操作错误；动态导入扫描无领域依赖 |
| 4. 通用 MCP | `integrations/cst-mcp/src/cst_mcp` 与测试 | 根级 `cst_mcp`、通用工具注册接口、开发者配置说明 | MCP 协议、写防护、结构化诊断测试；导入及工具不要求 TPC；不修改用户配置 |
| 5. 技能与说明 | 源 CST skill、开发流程、环境/弹窗文档 | `skills/cst-modeling`、`cst-simulation`、`cst-results`、`cst-diagnostics`；安装、脚本、MCP、故障定位指南 | 每个 skill 有短入口；无 mesh_grid 字体或拓扑手册硬依赖 |
| 6. 构建、隔离与交付 | 本仓库代码与相邻仓库公开实现 | `docs/VALIDATION.md`、审阅结果、本地提交；GitHub private 仓库（若账户/权限允许） | 构建 wheel/sdist；干净隔离环境从制品安装并运行导入/API测试；记录真实跨包结果或精确缺口；不运行真实 solver |

## 技术决策

- 保留源包导入名并用 setuptools 单一发行包 `cst-automation`；MCP 和开发工具设为 optional extra。CST 不作为 pip 依赖。
- MCP 源从嵌套 `integrations/cst-mcp/src/cst_mcp` 迁至根级 `cst_mcp`，保持用户 import 名。测试相应调整为独立根布局。
- `tpc_service.backends.cst_backend.CstBackend` 只操作现有 CST 工程，不再解析任何领域模型配置。领域构建/扫描由注册 handler 完成，默认无 handler 时明确失败。
- 仓库内部提供本地相邻源码开发说明；正式 pyproject 只声明发布版本区间，不绑定本机绝对路径。
- 迁移时保留源 MIT license 与归属信息；第三方 CST Runtime API 参考件不是本仓库必需运行资源，不复制原始实验文件、缓存或源仓库完整 README。

## 风险与审阅点

- `tpc_service` 的持久化状态和单 worker 语义是既有公共行为；改造 handler 时不得改变任务恢复、取消或 `saved=True` 守卫。
- 原 `cst_mcp` 工具目前以拓扑模板为领域；通用工具拆分要把协议边界和通用数据分析实现单独测试，不能因保留名字就保留领域逻辑。
- `cst_solver` 文档和 docstring 含 `topo_modeler` 引用：只有语义为“示例/调用者”时才替换为领域无关术语；不修改公开错误码与行为。
- wheel/sdist 测试必须清除 `PYTHONPATH` 和源仓库路径；若缺相邻包，标为尚未进行真实跨包验证。
- CST 安装、DLL、ABI 依赖无法由离线 mock 证明；真实机器 readback/solver 不属于本次验收范围。

## 执行记录

- [x] 读取拆分决策和本仓库约定；确认源仓库当前未提交工作状态无法由 Git 正常查询。
- [x] 先明确并公开领域 handler 协议（`docs/PUBLIC_API.md`）。
- [x] 建立忽略的源状态快照与逐文件迁移清单。
- [x] 迁移、解耦并完成离线测试（485 passed；9 条默认端口朝向警告）。
- [x] 构建 wheel/sdist 并在隔离目录安装验证（见 `docs/VALIDATION.md`）。
- [x] 迁移补充提交已推送；2026-10-27 核验远程 main 为 `07279b0`，对应 CI 成功。后续维护与真机证据见 `docs/VALIDATION.md`。
