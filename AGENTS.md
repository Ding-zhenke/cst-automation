# 项目约定

- 职责：通用 CST 建模、仿真、结果读取、通用任务运行和诊断。
- 不依赖 TPC 或 em-enclosure；通用包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`tpc_toolkit` 或 `em_enclosure`。
- Python 导入名保留为 `cst_solver`、`tpc_service`、`cst_mcp`；共享数据 API 位于 `cst_automation`。
- CST 自带的 `cst` 模块不作为 PyPI 依赖。常规导入不连接 CST；真实 SDK 只在执行 CST 操作时加载。
- 变更跨包协议前先更新 `docs/PUBLIC_API.md`，保持 handler 和 MCP 扩展显式注册。
- 执行本仓库任务前，先阅读 `skills/README.md`，再按任务读取对应的 `skills/<name>/SKILL.md`。技能统一保存在仓库根目录的 `skills/`，由本文件指引读取。
- 用户禁止将技能头几十行或搜索命中当作完整阅读。所选 `SKILL.md` 必须读至末尾，并读完当前操作要求的引用章节；工具输出被截断时连续补读缺失部分，补齐前不得提交依赖该规则的模型写入或求解。上下文压缩后只有摘要而无完整规则时，先重新读取；不让用户提醒补读，不用“已读”标记或文件摘要冒充阅读完成。
- 跨轮次建模、EM→HB 和优化任务按 `skills/cst-sessions/references/workflow-checkpoint.md` 保存并恢复当前要求、输入依赖及证据；用户纠正后先更新清单，依赖阶段提交前检查，不能用旧输入的通过记录放行新参数。
- Codex 对话实际操作 CST 默认先读 `skills/cst-sessions/SKILL.md`：每对话独立恢复引用、worker、DE 与工程目录；固定本仓库 `work/sessions` 根目录，后续复用，只有用户明确要求才关闭。中断先查原任务并恢复，不无 PID attach、不重复复制或重放未知建模阶段；未启用会话 MCP 时使用同一 `.venv` 的会话 CLI。
- 几何操作先根据真实参数给用户预览并等待审阅；再按依赖阶段 rebuild、读消息和记录产物。
- 几何检查、结果读取与实际求解分别记录证据，不因迁移、离线测试或 API 调用提高验证等级。
- CST 弹窗需读取实际标题、正文、按钮和进程归属；不凭等待超时或关闭弹窗推断成功。
- 使用本仓库 `.venv` 或隔离测试目录；不修改相邻仓库、用户全局 MCP 配置或公共 Python 环境。
- 迁移源 `D:\成电博士生涯\自动建模算法尝试\TPC` 严格只读；所有备份、构建、测试和开发产物放在本仓库，`work/` 忽略且不发布。
- GitHub 私有仓库已创建，初始提交已推送到 `origin/main`；后续本地提交由主会话统一推送。默认在 `main` 提交并推送；除非用户另行明确要求，不创建或推送修复分支。CST 真机 readback 与 solver 验收状态以 `docs/VALIDATION.md` 为准。
