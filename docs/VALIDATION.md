# 验证记录

记录 `cst-automation` 0.1.0 拆分实现的离线验证。几何 API 检查、结果读取和真实 CST 求解分开判定。

## 源状态与隔离

- 源仓库：`D:\成电博士生涯\自动建模算法尝试\TPC`，HEAD `51e4a63d302f0deea58d2a2df349892087dbdfe7`，remote `https://github.com/Ding-zhenke/TPC.git`。
- 对源目录执行只读 Git 状态查询时，Git 返回 `fatal: this operation must be run in a work tree`。迁移前把 111 个相关源码、测试、文档和许可证文件复制到目标仓库忽略的 `work/source-snapshot/`，并记录 SHA-256 清单及可读取的 HEAD/remote。无法据此声称源仓库干净；源目录没有被迁移脚本写入或清理。
- 所有测试从本仓库副本执行，并设置 `PYTHONDONTWRITEBYTECODE=1`、`python -B`，pytest 临时文件放在被忽略的 `work/pytest-tmp/`。

## 离线测试

```powershell
$env:TEMP = Join-Path (Get-Location) 'work\pytest-tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -o addopts='' -q
```

结果：**484 passed, 9 warnings**。警告来自端口 VBA 测试对未提供 orientation 时默认朝向提示的验证，不是失败。测试用 fake backend、stub CST 模块和离线文件；没有打开 CST 或用户工程。

## MCP 与技能

- MCP 子套件：`python -B -m pytest cst_mcp/tests -xvv`，**31 passed**。覆盖工具 schema/annotations、请求处理器注册、写操作隔离、分析与报告；没有完成 stdio/网络传输握手验证。
- 四个 `.github/skills/cst-*` 入口使用 skill-creator 的 `quick_validate.py` 按目录校验；每个入口均通过。

## 发行制品

```powershell
python -B -m build --no-isolation --wheel --sdist
```

结果：构建成功，输出 `dist/cst_automation-0.1.0-py3-none-any.whl` 与 `dist/cst_automation-0.1.0.tar.gz`。setuptools 在当前 Anaconda 环境打印 `bdist_conda` 可选 entry point 导入提示；该提示未阻止制品生成。许可证元数据使用 SPDX 字符串 `MIT`。

wheel 使用本地 `.venv` 安装后，在独立工作目录导入 `cst_solver`、`cst_automation`、`tpc_service` 和 `cst_mcp`。`importlib.util.find_spec` 返回的四个包路径均位于 `.venv/Lib/site-packages/`。该环境继承系统 site-packages 供 NumPy 等依赖使用，但发行包来自刚构建的 wheel。

## 跨仓库接口与证据边界

- 只读检查 `E:\Autocode\TPC\pyproject.toml` 与 `E:\Autocode\em-enclosure\pyproject.toml`：两个目标都声明可选 extra `cst = ["cst-automation>=0.1,<1"]`，与本包首发版本约定一致。
- 本轮没有安装并联调相邻仓库，也没有修改它们；因此不报告真实跨包调用通过。
- 没有在 CST Studio Suite 中执行真实几何重建、结果 readback 或求解。fake/mock、导入和制品安装均不构成这些验证。
- GitHub 登录身份为 `Ding-zhenke`，同名仓库检查为 404。浏览器已打开 `github.com/new`，但页面要求 2FA 验证；本环境没有 `gh` CLI，GitHub 连接器没有创建仓库接口。因此尚未创建远端或推送；需要用户完成 GitHub 2FA 后再继续发布。
