# MCP 使用

安装 MCP extra 后可运行 `python -m cst_mcp`，由宿主 MCP 客户端负责启动 stdio 进程。服务不安装或修改用户级/全局 MCP 配置。

通用工具包含 CST 能力发现、工程登记、已有工程求解、任务状态/结果读取、S 参数 CSV 分析和报告导出。写操作通过 `tpc_service.RunService`，MCP stdout 仅用于协议。领域包可在自有入口显式调用 `cst_mcp.register_tool(name, definition, handler)` 注册领域工具；未注册时不会导入拓扑或腔体代码。

调试时先将 `CST_AUTOMATION_WORKDIR` 指向可写的任务目录。`CST_AUTOMATION_BACKEND=fake` 可验证离线工具流；FakeBackend 会明确标记假结果。生产运行不要用 fake 结果代表 CST solver 输出。工具和 handler 协议见 [PUBLIC_API.md](../PUBLIC_API.md)。
