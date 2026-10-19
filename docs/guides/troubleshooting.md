# 故障定位

## CST 安装或 SDK 导入

- 运行 `python -m cst_solver doctor --json`，保存原始 JSON。
- `not_found`：核对安装目录和环境变量；库不会假定用户机器路径。
- ABI 不匹配：切换到 CST Python 扩展支持的 Python 版本；ABI 文件存在不代表 DLL 加载成功。
- `ImportError`/DLL 错误：保留异常链、解释器路径、CST 安装路径和 ABI 报告；不要将此类失败误报为模型失败。

## 阻塞或 CST 弹窗

读取 `runtime_diagnostics` 中的窗口正文、标题、按钮、PID 和进程信息。先确认 SDK 调用是否仍在原线程；不要重复提交相同写任务。仅在弹窗内容明确且操作安全时响应。确认后重新读取任务状态；弹窗关闭不等于 solver 成功。

## 几何和求解

先查 `cst_solver` 结构化失败、guard finding、操作日志和 CST 工程路径。几何错误用最小依赖阶段复现并 rebuild；求解只有 `run_checked` 明确返回成功、结果已保存并有对应 run identity 才记录为 solver 成功。离线假后端、文件存在、结果树可读取都不能替代这些证据。

更多环境和弹窗细节见 [cst_environment.md](cst_environment.md) 与 [cst_dialogs.md](cst_dialogs.md)。
