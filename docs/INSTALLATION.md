# 安装与本机 CST 配置

## Python 包

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mcp]"
```

基础安装带有数值解析所需的 NumPy；MCP SDK 与测试/构建工具由 optional extras 安装。MCP extra 使用 SDK 1.x 且要求 Python 3.10+；Python 3.9 可使用核心包和离线 API。CST 的 `cst` 模块由本机 CST Studio Suite 安装提供，不要尝试 `pip install cst`。

## CST Studio Suite

1. 使用与本机 CST Python 扩展 ABI 兼容的 Python 解释器。
2. 运行 `python -m cst_solver doctor --json` 检查自动发现、配置来源、接口 ABI 和 SDK 导入状态。
3. 如自动发现失败，按 [CST 环境说明](guides/cst_environment.md)配置 `CST_INSTALL_PATH`、`CST_PYTHON_LIB`、`CST_MATERIAL_LIB`；库本身不会硬编码任何个人目录。
4. 重新运行 doctor 验证配置。ABI 匹配不代表 DLL 已成功加载，也不代表真实求解已验证。

## 本地开发

```powershell
python -m pip install -e ".[dev,mcp]"
python -m pytest -o addopts='' -q
python -m build --wheel --sdist
```

相邻 TPC/em-enclosure 源码可各自在自己的开发环境 editable 安装此仓库。正式依赖通过 PyPI 版本范围声明；不要把 E: 或 D: 盘路径放进已发布配置。
