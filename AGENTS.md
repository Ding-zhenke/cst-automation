# 项目约定

- 职责：通用 CST 建模、仿真、结果读取、通用任务运行和诊断。
- 不依赖 TPC 或 em-enclosure；通用包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`tpc_toolkit` 或 `em_enclosure`。
- Python 导入名保留为 `cst_solver`、`tpc_service`、`cst_mcp`；共享数据 API 位于 `cst_automation`。
- CST 自带的 `cst` 模块不作为 PyPI 依赖。常规导入不连接 CST；真实 SDK 只在执行 CST 操作时加载。
- 变更跨包协议前先更新 `docs/PUBLIC_API.md`，保持 handler 和 MCP 扩展显式注册。
- 几何操作先根据真实参数给用户预览并等待审阅；再按依赖阶段 rebuild、读消息和记录产物。
- 几何检查、结果读取与实际求解分别记录证据，不因迁移、离线测试或 API 调用提高验证等级。
- CST 弹窗需读取实际标题、正文、按钮和进程归属；不凭等待超时或关闭弹窗推断成功。
- 使用本仓库 `.venv` 或隔离测试目录；不修改相邻仓库、用户全局 MCP 配置或公共 Python 环境。
- 迁移源 `D:\成电博士生涯\自动建模算法尝试\TPC` 严格只读；所有备份、构建、测试和开发产物放在本仓库，`work/` 忽略且不发布。
- 当前拆分实现已在本地工作区；GitHub 私有发布、CST 真机 readback 与 solver 验收状态以 `docs/VALIDATION.md` 为准。
