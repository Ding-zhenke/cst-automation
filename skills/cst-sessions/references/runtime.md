# 环境与能力边界

插件提供工作流，不包含 Python 库、CST SDK、许可证或设备模型。使用目标工作区授权的虚拟环境，不修改公共 Python 环境、全局 MCP 配置或其他项目。CST 的 cst 模块随安装提供，不从 PyPI 安装。

执行前核对 cst-automation 的版本、模块位置和实际 API。以该版本 docs/PUBLIC_API.md 和源码确定签名；本文列出的扩展可能晚于已安装版本。缺少能力时报告准确缺项，保持离线规划，不假造工具、不自动安装新版本。

诊断时，`python -m cst_solver doctor --json` 只检查配置、路径和 ABI，可在沙箱内运行。加 `--probe` 会导入原生 SDK，首次调用就使用能访问 CST 许可证的沙箱外宿主；通过 Codex 命令工具启动时指定 `sandbox_permissions="require_escalated"`。检查返回的导入状态和错误；许可证可用性、工程读回和求解各需相应证据。

会话模块为 tpc_service.sessions；电路为 cst_solver.circuit；数据处理为 cst_automation；MCP 为 cst_mcp。模块名是兼容接口，不表示依赖其他领域仓库。先查帮助/能力，普通导入不连接 CST。

优先已有 Python API；没有封装且有当前版本依据时补最小 VBA。界面用于实际弹窗或必要原生显示检查，不替代可读取日志和数据。

分别报告离线预检、配置提交、原生读回、重建、指定运行、数值充分性和器件性能；保留 unknown/unverified/未执行。fake 只验证软件链路。

模型参数、材料/器件值、源条件、扫描点、工程路径和历史结果保存在当前项目，不写入插件、通用示例或共享样式。
