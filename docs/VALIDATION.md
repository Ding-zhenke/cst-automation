# 验证记录

记录 `cst-automation` 0.1.0 的拆分历史及后续验证。几何 API 检查、结果读取和真实 CST 求解分开判定。本地运行与 GitHub Actions 运行分别记录，不能相互替代。

## 2026-11-02 CST 2026 API 离线修复

### 消息三态契约修复与推送前验证

- 实施 not_read/read/read_failed：messages_clean 为 bool|None，未读不再由空列表判成功；保留部分迭代消息与读取异常，明确 caller/callback/sdk_pending_queue 来源。原生 solver、原生日志警告和 mesh 收敛无读取证据时仍为 unknown。
- 新增 23 项离线测试，包含 RunContract/run_checked 禁读及成功/失败读取、JSONL、独立运行之间状态隔离、错误参数不触发提交、后端/服务落盘/MCP 查询传播，以及保存失败仍保留运行契约和 run token。
- 完整回归：`.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/adaptive-results/pytest`：**572 passed, 2 skipped, 1 deselected, 9 warnings**。2 项 MCP 协议/stdio 测试因缺少 extra 跳过；服务及 MCP dispatch 状态传播测试已通过。没有安装依赖或改变当前运行环境。
- 代码复核发现保存失败会丢运行证据，已补失败回归并修复；当前改动不宣称真机验收。用户授权提交和推送当前专用分支，未授权合并 main 或部署安装环境。
- 来源会话只读确认 `Mesh\Information\Element Information\Low Quality Elements` 可原生可视化定位；数值 ID/坐标/质量导出仍未证实，详见网格诊断能力文档。本会话未连接其检查会话。

### 联合枚举与 Pass 轴读取补充

- 实现 `Result.enumerate_result_paths`、`read_adaptive_s_parameter` 和 `read_adaptive_s_parameters`，通过独立 mixin 接入，保留现有树枚举签名；普通 S 参数发现限制到主频率结果树。
- 新增 45 项离线测试，使用显式 results/modeler 替身，禁止隐式 SDK 加载/会话构造。覆盖重复路径来源合并、枚举中断/失败、modeler-only 路径、同一 run 下逐轮复数数据、显式/错误/当前别名 run、Pass 轴与非法数组、参考阻抗原样保留及未知归一化、单位原文与冲突、部分读取错误、空结果及不混入普通频率批量读取。
- `.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/adaptive-results/pytest`：**549 passed, 2 skipped, 1 deselected, 9 warnings**。MCP extra 缺失和 GUI 排除与前次一致；测试产物在 work/。这不增加原生 readback 或求解验收等级。
- 未连接、启动、关闭 CST，未读取来源工程，未修改全局环境或插件缓存。原生参考阻抗的数据形态、工程身份对应和新接口完整闭环仍需在已授权主机环境串行验收；来源会话此前已核实的路径/轴语义与本轮实现的离线测试分别记录。

### 前序通用修复记录

- 分支：`codex/cst-2026-offline-api-repairs`；未推送，未更新全局安装或插件缓存。
- 本轮不连接、启动、关闭 CST，不读取或修改另一会话工程，不中断其求解。未检查或声称全机空闲。
- 本机官方帮助核对了点端口 Voltage/Current、picked 参数、面端口不同的幅度方法、CircuitProbe/Net 对象及 continuation 的文档边界。
- 新增 17 项离线回归：点端口宏、执行器选择与不重试、CircuitProbe/Net 宏、Delta S 多频率/连续轮次判定、装饰窗与未知状态、确认前 PID 创建身份复核、主机预检查拒绝与服务错误码。修复一个既有测试对临时目录父路径为 ASCII 的假设，以支持在本仓库中文路径下运行所有测试产物。
- 本仓库 `.venv` 实际为 Python 3.9.18；补齐该隔离环境的 pip/NumPy/pytest，未修改公共 Python。执行 `.venv/Scripts/python.exe -m pytest -ra --disable-warnings --basetemp=work/api-offline-repairs/pytest`：**504 passed, 2 skipped, 1 deselected, 9 warnings**。2 项 MCP 协议/stdio 测试因未安装 MCP extra 跳过（该 extra 要求 Python >=3.10）；1 项 GUI 测试不运行；9 项为既有端口朝向提示。`git diff --check` 无错误。
- 离线 `doctor --json` 发现本机 CST 2026 与 cp39 ABI 匹配，状态为 `not_probed`；没有执行 `--probe`，不声称 SDK 导入、IPC、许可、readback 或 solver 已验证。
- 本轮没有找到公开显式选择 CONTINUE 的已文档化 Python/VBA 方法；ForceRecalculateOldSamples/AcceleratedRestart/resume_solver 不能作为该能力的证明。未实现或声称原生网格 continuation 可用。
- 主机 preflight 为新增 opt-in 入口，既有 setup/服务尚未迁移；收敛评价器处理调用方提供的证据，未实现原生自适应结果提取；Qt 非标准确认按钮与不可读正文仍上报，不自动处理。新增连接、暂停、停止案例仅记录来源会话报告，未复测。
- 调用示例、官方帮助相对路径和逐项真机待验清单见 [API 修复说明](guides/api-offline-repairs.md)。真机验收须等待其他求解结束，并持有全机串行锁、核对 PID+创建时间、在可访问主机环境执行。
- 来源会话后续报告：中止完成、控制器退出，但恢复最后成功解后出现离散面端口解加载失败，原生 state 为 ERROR，不计完整矩阵或求解通过。ItemMeshSettings 是返回 bool 的上下文变更调用，误作 getter 属使用方语义错误；求解器自动生成特殊体不支持 simple bounding box 的情况须与普通几何损坏分开记录。以上仅补充记录，未复测；主任务即将继续，不据此认定全机空闲或取得真机使用授权。
- 逐轮结果结论更正（来源会话真机只读核实，本会话未连接）：Model3D 树枚举可发现 Python results 树列表漏列的 `1D Results\Adaptive Meshing\f=<frequency>\S-Parameters\S<i>,<j>`；这些条目可由 Python results 按已有 run ID 读取，xlabel 为 Pass、y 为每轮复数 S。来源会话已全量读回并复现原生 Delta All S、核对末轮主矩阵及归一化。不能再以 run ID 未增加或 Python 树漏列断言无逐轮数据；后续联合枚举须显式使用已授权会话，不能隐式连接。本轮仅记录通用语义，未新增实现或纳入具体矩阵数据。

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
