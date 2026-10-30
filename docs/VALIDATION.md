# 验证记录

记录 `cst-automation` 0.1.0 的拆分历史及后续验证。几何 API 检查、结果读取和真实 CST 求解分开判定。本地运行与 GitHub Actions 运行分别记录，不能相互替代。

## 2026-10-27 维护验证

- **Git 来源已恢复**：本机目录原为不含 `.git` 的源码副本。先保存文件快照，再在 `work/maintenance-20261027/upstream/` 克隆完整仓库并恢复根目录 Git 元数据；重建索引时保留全部工作文件。维护前远程 main 为 `07279b078af3484f6f0ad8c0ed6c9ed02db702f5`。该提交的 [Actions 40395424088](https://github.com/Ding-zhenke/cst-automation/actions/runs/40395424088) 已成功；这不是当前维护改动的 CI 结果。
- **维护提交的远程 CI**：分支 `codex/portable-environment-validation` 的提交 `adf187b3fa254554effb7d328fd8e7a71b529538` 已推送；[Actions 40399304203](https://github.com/Ding-zhenke/cst-automation/actions/runs/40399304203) 的 Python 3.9、3.11、MCP 和 build（包含全新环境的 wheel 安装与 stdio 检查）四个 job 全部成功。修复及本记录通过 [草稿 PR #2](https://github.com/Ding-zhenke/cst-automation/pull/2) 提交审阅，未合并到 main。
- **环境与 CLI**：发行包的兼容 `config.py` 不再携带机器路径；离线检查对缺失 SDK 目录、未发现 SDK、选中安装已知 ABI 不匹配报告 `unavailable` 并退出 1。`doctor --json` 已支持，默认仍输出 JSON。测试验证了未配置时发现安装、显式无效路径不回退、JSON 输出、退出码及自定义 SDK 的 ABI 归属。
- **离线回归**：仓库 `.venv`（Python 3.13.9，不继承系统包）执行 `python -B -m pytest -o addopts='' -m "not gui" -q -p no:cacheprovider --basetemp=work/maintenance-20261027/pytest-full`：**490 passed, 1 deselected, 9 warnings**。警告仍为端口默认朝向提示；GUI 用例未运行。
- **SDK 导入**：显式设置 `CST_INSTALL_PATH=E:\CST2026` 后，Python 3.13.9 / CST 2026 的 cp313 匹配，`doctor --probe` 实际导入 `cst.interface` 和 `cst.results` 成功，状态为 `importable`。该路径是本机验证参数，不是发行默认值；不代表许可证、readback 或 solver 已通过。
- **MCP stdio**：新增真实子进程集成测试，使用 MCP Python SDK 1.30.0，完成初始化、9 个工具发现、读写注解、能力调用、未知工具/参数错误、假后端任务排队/状态/结果与关闭工程。测试阻止实际加载 CST，且检查请求 `run_id=7` 能原样返回；同时修复 FakeBackend 固定返回 run ID 0 的问题。通过的是 stdio 与 fake 任务链路，本包没有实现网络传输入口，不声称网络传输通过。
- **发行制品**：构建 wheel 和 sdist 成功；构建后端最低版本改为支持 SPDX license 字符串的 `setuptools>=77`。制品不含 `work/`、`.venv/`、源码备份或 Git 元数据，wheel 内配置无机器路径。
- **干净安装**：`work/maintenance-20261027/release-venv/` 由 `venv` 新建，`include-system-site-packages = false`；安装刚构建的 wheel 及声明的 NumPy/MCP 依赖。独立目录中清除 `PYTHONPATH`，四个包的加载路径均在该环境 `site-packages`，普通导入不改 `sys.path`、不加载 `cst`。曲线调用、缺失 SDK 的 doctor 退出码 1、安装版 stdio 握手/9 个工具发现/结构化错误均通过。可复用检查脚本为 `scripts/verify_wheel.py`；CI 的 build job 也执行该隔离安装检查。
- **尚未验收**：真实 CST 几何重建、实际消息/UIA、S 参数结果树发现、远场导出、solver，以及相邻领域仓库联调。具体几何参数、端口及阶段证据方案见 [真机验收预览](REAL_CST_ACCEPTANCE.md)，等待用户审阅后才构造几何。运行中取消接口仍未开放。
- 原始快照、构建日志、环境报告及隔离安装报告保存在被忽略的 `work/maintenance-20261027/`；本轮不修改相邻仓库或用户全局 MCP 配置。

## 迁移阶段历史记录

以下为拆分阶段保留的历史结果，环境、依赖版本与当时的推送状态不能作为本轮的新证据。

## 源状态与隔离

- 源仓库：`D:\成电博士生涯\自动建模算法尝试\TPC`，HEAD `51e4a63d302f0deea58d2a2df349892087dbdfe7`，remote `https://github.com/Ding-zhenke/TPC.git`。
- 对源目录执行只读 Git 状态查询时，Git 返回 `fatal: this operation must be run in a work tree`。迁移前把 111 个相关源码、测试、文档和许可证文件复制到目标仓库忽略的 `work/source-snapshot/`，并记录 SHA-256 清单及可读取的 HEAD/remote。无法据此声称源仓库干净；源目录没有被迁移脚本写入或清理。
- 所有测试从本仓库副本执行，并设置 `PYTHONDONTWRITEBYTECODE=1`、`python -B`，pytest 临时文件放在被忽略的 `work/pytest-tmp/`。

## 离线测试

```powershell
$env:TEMP = Join-Path (Get-Location) 'work\pytest-tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest -o addopts='' -m "not gui" -q
```

本次修复后的本地运行：**484 passed, 1 deselected, 9 warnings**。唯一 deselected 项是 `test_native_body_is_reported_while_message_box_is_open`，它通过真实 Win32 消息框和 PowerShell UI Automation 检查桌面可访问性，标记为 `gui`，仅在交互式 Windows 会话中 opt-in 运行：

```powershell
python -B -m pytest -o addopts='' -m gui -q cst_solver/tests/test_dialog_windows.py
```

普通 pytest 默认排除 `gui` 标记，CI 命令也显式排除。离线测试使用 fake backend、stub CST 模块和离线文件；没有打开 CST 或用户工程。9 条警告来自端口 VBA 测试验证未提供 orientation 时的默认朝向提示，不是失败。

## GitHub Actions 故障诊断

- 首次 Actions 运行 [39219977888](https://github.com/Ding-zhenke/cst-automation/actions/runs/39219977888) 中，Python 3.9 核心测试 **481 passed, 1 skipped, 1 failed**。失败是 `test_interface_abi_match_is_reported_offline` 的测试数据重复：在 Python 3.9 上，硬编码 `cp39` 与运行时 ABI 标签相同；被测接口目录只会枚举到一个 `cp39` 文件。修复后的测试显式固定 `cp39` 作为运行时标签，并对发现的接口 ABI 去重后比较；本地回归测试通过。
- 同一运行的 Python 3.11 核心测试为 **481 passed, 1 skipped, 1 failed**。唯一失败是上述真实桌面 UIA 测试在 hosted runner 的 PowerShell bridge 上 4 秒超时。该检查依赖交互式 Windows 桌面，不能作为离线 CI 测试；现在它标记为 `gui` 并从默认测试和 CI 排除，仍可在本地交互式 Windows 会话中显式运行。没有修改生产 UIA 逻辑或放宽其超时。
- 构建和 MCP Actions job 在该次运行成功。该运行的 checkout/setup-python 步骤还报告 Node 20 弃用告警；工作流现改用 `actions/checkout@v7.0.1` 与 `actions/setup-python@v7.0.0`。
- 上述 Actions 结果是修复前的远程证据。后续修复已推送，`b2ba37b` 的 [Actions 39229502176](https://github.com/Ding-zhenke/cst-automation/actions/runs/39229502176) 和 `07279b0` 的 Actions 均成功；不能把这些运行归于后续维护提交。

## MCP 与技能

- MCP 子套件：`python -B -m pytest cst_mcp/tests -xvv`，此前运行 **31 passed**，使用 MCP Python SDK 1.29.1。项目 extra 声明 `mcp>=1.29,<2` 且限 Python 3.10+，以匹配已测试的 1.x server API；没有完成 stdio/网络传输握手验证。
- 四个 `skills/cst-*` 入口使用 skill-creator 的 `quick_validate.py` 按目录校验；每个入口均通过。

## 发行制品

```powershell
python -B -m build --no-isolation --wheel --sdist
```

结果：构建成功，输出 `dist/cst_automation-0.1.0-py3-none-any.whl` 与 `dist/cst_automation-0.1.0.tar.gz`。setuptools 在当前 Anaconda 环境打印 `bdist_conda` 可选 entry point 导入提示；该提示未阻止制品生成。许可证元数据使用 SPDX 字符串 `MIT`。

wheel 使用本地 `.venv` 安装后，在独立工作目录导入 `cst_solver`、`cst_automation`、`tpc_service` 和 `cst_mcp`。`importlib.util.find_spec` 返回的四个包路径均位于 `.venv/Lib/site-packages/`。该环境继承系统 site-packages 供 NumPy 等依赖使用，但发行包来自刚构建的 wheel。

## 跨仓库接口与证据边界

- 只读检查 `E:\Autocode\TPC\pyproject.toml` 与 `E:\Autocode\em-enclosure\pyproject.toml`：两个目标都声明可选 extra `cst = ["cst-automation>=0.1,<1"]`，与本包首发版本约定一致。
- TPC 和 em-enclosure 的 handler 注册形态与 `RunService.register_handler(kind, handler, *, replace=False)` 相符。TPC 现有 `_guards` 调用点有对应实现；本包现新增稳定公开入口 `cst_solver.guards`，本轮不改写 TPC 源调用点。
- 本轮没有安装并联调相邻仓库，也没有修改它们；因此不报告真实跨包调用通过。
- 没有在 CST Studio Suite 中执行真实几何重建、结果 readback 或求解。fake/mock、导入和制品安装均不构成这些验证。
- GitHub private 仓库 `Ding-zhenke/cst-automation` 已创建；初始提交 `1e00a1f` 当时已在 `origin/main` 核验。迁移补充提交后来已推送，维护前最新 main 和对应 CI 见本页顶部的 2026-10-27 核验。
