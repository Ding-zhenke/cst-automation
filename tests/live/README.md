# CST 电路实机验证

默认测试排除 `cst_live`，测试收集不加载 CST。当前可执行用例只读取已保存的电路曲线，不建模、不求解，且不能证明本轮求解完成。

用户审阅几何与端口预览后，再按设计 V1–V7 的顺序进行实机验证。设置 `CST_CIRCUIT_LIVE=1`、`CST_CIRCUIT_SAVED_PROJECT`、`CST_CIRCUIT_TREE_PATH`、`CST_CIRCUIT_RUN_ID`，然后显式运行：

```powershell
.venv/Scripts/python.exe -B -m pytest tests/live -o addopts='' -m cst_live -q
```

工程只使用本仓库 `work/` 中的副本。2026-10-19 的阶段脚本和原始证据位于 `work/circuit-validation/20261019-live/`，V1/V2/V3 已实际执行，V4 因 DS 采样插值警告保持严格未验证，V5 未启动，V6/V7 仅部分范围通过。参见 [实机记录](../../docs/CIRCUIT_LIVE_REPORT.md)。本文件的 pytest 用例只证明已保存曲线可以读取，没有用它或跳过的测试冒充求解完成。
