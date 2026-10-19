# cst-automation

通用 CST Studio Suite 建模、仿真、结果读取、任务运行和诊断库。保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，并提供 CST 无关的数据工具 `cst_automation.curves` 与 `cst_automation.s2p`。核心包支持 Python 3.9+，依赖 NumPy；MCP 服务器 extra 需要 Python 3.10+。

## 安装

```powershell
python -m pip install ".[mcp]"
python -m cst_solver doctor --json
```

CST 的 `cst` Python 模块必须由本机 CST Studio Suite 提供，不是 PyPI 依赖。MCP extra 固定在 SDK 1.x（`mcp>=1.29,<2`），适配当前服务实现。

## 离线使用

下面的曲线分析可在没有 CST 的机器执行：

```python
from cst_automation.curves import contiguous_bands

freqs_ghz = [1.0, 1.1, 1.2, 1.3]
s11_db = [-16.0, -18.0, -4.0, -17.0]
bands = contiguous_bands(freqs_ghz, s11_db, threshold_db=-10.0)
print(bands)
```

开发依赖和完整离线测试：

```powershell
python -m pip install -e ".[dev,mcp]"
python -m pytest -o addopts='' -m "not gui" -q
python -m build --wheel --sdist
```

常规测试使用 fake/stub，不要求安装 CST，并排除需要交互式 Windows 桌面的 `gui` 标记测试。桌面集成测试需在可交互的 Windows 会话中显式运行：`python -m pytest -o addopts='' -m gui -q cst_solver/tests/test_dialog_windows.py`。服务 handler 的最小例子见 [Python 使用指南](docs/guides/python-usage.md)。

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
- [仓库 skills](skills/README.md)
- [贡献指南](CONTRIBUTING.md)

使用 Codex 处理本仓库任务时，先打开 [skills 索引](skills/README.md)，再按任务读取对应的 `SKILL.md`。仓库技能保存在 `skills/`，由 `AGENTS.md` 指引读取。

本项目按 [MIT License](LICENSE) 发布。
## Design Studio 扩展状态

`0.2.0.dev0` 增加原理图、电路任务、独立电路结果、依赖清点、服务和 MCP 的显式接口。CST 2026.1 已实测纯电路、批准的三维样例及三种线性 network 负载。真实瞬态联合取得两侧运行和波形证据，但采样插值警告未消除，严格验收仍未通过；非线性、通用映射、缓存及外部工程搬运不推定支持。详见 [分阶段实机记录](docs/CIRCUIT_LIVE_REPORT.md)。

见 [电路接口指南](docs/guides/circuit_cosimulation.md) 和 [验证记录](docs/VALIDATION.md)。三维样例须先审阅预览，再建模求解。
