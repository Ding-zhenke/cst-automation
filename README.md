# cst-automation

通用 CST Studio Suite 建模、仿真、结果读取、任务运行和诊断库。保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，并提供 CST 无关的数据工具 `cst_automation.curves` 与 `cst_automation.s2p`。

## 安装

```powershell
python -m pip install "cst-automation[mcp]"
python -m cst_solver doctor --json
```

CST 的 `cst` Python 模块必须由本机 CST Studio Suite 提供，不是 PyPI 依赖。离线工作可以导入/分析数据或用 `FakeBackend` 检查任务工作流。

## 边界

- 通用库不依赖 TPC 或 em-enclosure；领域构建和研究任务由包调用方注册 handler。
- 导入与数据解析不会启动 CST；CST SDK 在真实 CST 操作时惰性加载。
- 几何 rebuild、结果 readback 与实际 solver 状态是分开的证据。FakeBackend 数据为合成值。
- 服务/handler/版本协议见 [docs/PUBLIC_API.md](docs/PUBLIC_API.md)；迁移范围见 [docs/MIGRATION_MAP.md](docs/MIGRATION_MAP.md)，验收状态见 [docs/VALIDATION.md](docs/VALIDATION.md)。

## 文档

- [安装与配置](docs/INSTALLATION.md)
- [Python 使用](docs/guides/python-usage.md)
- [MCP 使用](docs/guides/mcp-usage.md)
- [故障定位](docs/guides/troubleshooting.md)
- [仓库 skills](.github/skills/README.md)
