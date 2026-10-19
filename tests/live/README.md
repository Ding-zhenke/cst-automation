# CST 电路实机验证

默认测试排除 `cst_live`，测试收集不加载 CST。当前可执行用例只读取已保存的电路曲线，不建模、不求解，且不能证明本轮求解完成。

用户审阅几何与端口预览后，再按设计 V1–V7 的顺序进行实机验证。设置 `CST_CIRCUIT_LIVE=1`、`CST_CIRCUIT_SAVED_PROJECT`、`CST_CIRCUIT_TREE_PATH`、`CST_CIRCUIT_RUN_ID`，然后显式运行：

```powershell
.venv/Scripts/python.exe -B -m pytest tests/live -o addopts='' -m cst_live -q
```

工程只使用本仓库 `work/` 中的副本。V1 原理图写入/保存重开、V2 电路求解、V3/V4 场路执行证据和 V5–V7 仍待后续实机阶段实现/校准；没有用跳过的测试冒充验收通过。
