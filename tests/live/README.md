# CST 电路实机验证

默认离线测试排除 `cst_live`。本目录的可执行用例只从已保存工程读取电路曲线。仅在当前任务明确要求这项实机读取时运行，先确认仓库 `work/` 下的工程副本、树路径、Run ID 和所属许可证宿主。本机 Codex 从第一次原生调用起指定 `sandbox_permissions="require_escalated"`，Windows 非交互 Python 从首进程起后台运行。

设置 `CST_CIRCUIT_LIVE=1`、`CST_CIRCUIT_SAVED_PROJECT`、`CST_CIRCUIT_TREE_PATH`、`CST_CIRCUIT_RUN_ID` 后，从仓库根目录运行：

```powershell
& .\skills\keysight-ads-simulation\scripts\invoke_hidden.ps1 -Executable .\.venv\Scripts\python.exe -ArgumentList @('-B','-m','pytest','tests/live','-o','addopts=','-m','cst_live','-q')
exit $LASTEXITCODE
```

2026-10-19 的 V1–V7 顺序属于当时经预览审阅的验收计划。V1/V2/V3 已执行，V4 因 DS 插值警告未通过严格验证，V5 未启动，V6/V7 只验证了部分范围。原始证据位于 `work/circuit-validation/20261019-live/`，详见[实机记录](../../docs/CIRCUIT_LIVE_REPORT.md)。新任务中的读取、建模、求解及数值结论各自按当次授权和证据判断。
